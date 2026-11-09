from datetime import date
from decimal import Decimal
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_optional_user, phone_from_token
from app.models import Category, Order, Product, Review, User
from app.schemas import (
    CartSyncIn,
    ChatSendIn,
    DeliveryZoneOut,
    OrderCreateIn,
    OrderLookupIn,
    OrderOut,
    ProductOut,
    PromoValidateIn,
    PromoValidateOut,
    ReviewIn,
    ReviewListOut,
    ReviewOut,
    SlotsOut,
)
from app.platform.sync import is_enabled
from app.security import format_phone, normalize_phone
from app.serializers import order_payload, product_payload
from app.services.audit import audit
from app.services import carts as cart_service
from app.services import chat as chat_service
from app.services import upsells as upsell_service
from app.services.orders import cancel_by_customer, create_order, get_slots
from app.services.promotions import resolve as resolve_promo
from app.services.delivery import (
    feature_enabled as delivery_enabled,
    serialize as delivery_zone_payload,
    zones as delivery_zones_list,
)
from app.services.qr import make_qr_png, product_url, site_url
from app.services.reviews import (
    attach_ratings,
    feature_enabled as reviews_enabled,
    list_published as list_published_reviews,
    make_review,
    public_payload as review_payload,
    summary as review_summary,
)
from app.services.settings import get_public_settings, get_settings_model, settings_updated_at
from app.security import decode_token
from app.tenancy import current_tenant, is_platform_host
from app.utils import iso, local_today
from app.platform import templates as design_templates


router = APIRouter(tags=["Публичный сайт"])


@router.get("/templates", summary="Дизайн-шаблоны витрины")
def list_design_templates():
    return [item.payload() for item in design_templates.DESIGN_TEMPLATES]


@router.get("/site", summary="Настройки сайта, категории и режим работы")
def site_info(db: Session = Depends(get_db)):
    conf = get_settings_model(db)
    tenant = current_tenant()
    categories = db.scalar(select(func.count()).select_from(Product).where(Product.is_active.is_(True))) or 0
    today_hours = next((h for h in conf.working_hours if h.weekday == local_today().weekday()), None)
    promo_enabled = False
    review_feature = False
    delivery_feature = False
    loyalty_enabled = False
    chat_enabled = False
    gift_enabled = False
    subscriptions_enabled = False
    if tenant:
        from app.platform.sync import is_enabled

        promo_enabled = is_enabled(db, tenant.id, "promo_codes")
        review_feature = is_enabled(db, tenant.id, "reviews")
        delivery_feature = is_enabled(db, tenant.id, "delivery")
        loyalty_enabled = is_enabled(db, tenant.id, "loyalty")
        chat_enabled = is_enabled(db, tenant.id, "support_chat")
        gift_enabled = is_enabled(db, tenant.id, "gift_certificates")
        subscriptions_enabled = is_enabled(db, tenant.id, "subscriptions")
    return {
        "tenant": (
            {
                "slug": tenant.slug,
                "name": tenant.name,
                "status": tenant.status,
                "plan": tenant.plan_code,
                "category_preset": tenant.category_preset,
                "locale": tenant.locale,
                "currency": tenant.currency,
                "timezone": tenant.timezone,
            }
            if tenant
            else None
        ),
        "settings": get_public_settings(db),
        "theme": design_templates.template_payload(conf.template, conf.accent_color),
        "features": {
            "promo_codes": promo_enabled,
            "reviews": review_feature,
            "delivery": delivery_feature,
            "loyalty": loyalty_enabled,
            "chat": chat_enabled,
            "gift_certificates": gift_enabled,
            "subscriptions": subscriptions_enabled,
        },
        "updated_at": iso(settings_updated_at(db)),
        "products_count": categories,
        "today": {
            "date": iso(local_today()),
            "open": today_hours.open if today_hours and not today_hours.closed else None,
            "close": today_hours.close if today_hours and not today_hours.closed else None,
            "is_closed": bool(today_hours.closed) if today_hours else True,
            "label": today_hours.label if today_hours else "",
        },
    }


@router.get("/categories", summary="Категории каталога")
def categories(db: Session = Depends(get_db)):
    from app.models import Category

    rows = db.scalars(select(Category).where(Category.is_active.is_(True)).order_by(Category.sort_order, Category.title)).all()
    counts = dict(
        db.execute(
            select(Product.category_id, func.count(Product.id))
            .where(Product.is_active.is_(True))
            .group_by(Product.category_id)
        ).all()
    )
    return [
        {
            "id": c.id,
            "slug": c.slug,
            "title": c.title,
            "description": c.description,
            "image_url": c.image_url,
            "sort_order": c.sort_order,
            "is_active": c.is_active,
            "products_count": int(counts.get(c.id, 0)),
        }
        for c in rows
    ]


@router.get("/products", summary="Каталог товаров")
def products(
    category: str | None = None,
    q: str | None = None,
    available_only: bool = False,
    sort: str = Query(default="default", pattern="^(default|price_asc|price_desc|new|title)$"),
    limit: int = Query(default=60, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    from app.models import Category

    final_price = Product.price * (100 - Product.discount_percent) / 100
    stmt = select(Product).where(Product.is_active.is_(True))
    count_stmt = select(func.count(Product.id)).where(Product.is_active.is_(True))

    if category:
        stmt = stmt.join(Category, Product.category_id == Category.id).where(Category.slug == category)
        count_stmt = count_stmt.join(Category, Product.category_id == Category.id).where(Category.slug == category)
    if q:
        pattern = f"%{q.strip()}%"
        clause = or_(Product.title.ilike(pattern), Product.short_description.ilike(pattern), Product.subtitle.ilike(pattern))
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)
    if available_only:
        stmt = stmt.where(Product.is_available.is_(True))
        count_stmt = count_stmt.where(Product.is_available.is_(True))

    if sort == "price_asc":
        stmt = stmt.order_by(final_price.asc())
    elif sort == "price_desc":
        stmt = stmt.order_by(final_price.desc())
    elif sort == "new":
        stmt = stmt.order_by(Product.created_at.desc())
    elif sort == "title":
        stmt = stmt.order_by(Product.title.asc())
    else:
        stmt = stmt.order_by(Product.sort_order.asc(), Product.id.asc())

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.offset(offset).limit(limit)).unique().all()
    items = [product_payload(p) for p in rows]
    attach_ratings(db, items)
    return {
        "items": items,
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }


@router.get("/products/{slug}", response_model=ProductOut, summary="Карточка товара и статья")
def product_detail(slug: str, db: Session = Depends(get_db)):
    product = db.scalar(select(Product).where(Product.slug == slug, Product.is_active.is_(True)))
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    payload = product_payload(product, include_article=True)
    attach_ratings(db, [payload])
    return payload


@router.get("/products/{slug}/reviews", response_model=ReviewListOut, summary="Отзывы о товаре")
def product_reviews(
    slug: str,
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    product = db.scalar(select(Product).where(Product.slug == slug, Product.is_active.is_(True)))
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    if not reviews_enabled(db):
        return {"items": [], "total": 0, "average": 0, "distribution": {}, "enabled": False}
    stats = review_summary(db, product.id)
    rows = list_published_reviews(db, product.id, limit=limit)
    return {
        "items": [review_payload(row) for row in rows],
        "total": stats["total"],
        "average": stats["average"],
        "distribution": stats["distribution"],
        "enabled": True,
    }


@router.post(
    "/products/{slug}/reviews",
    response_model=ReviewOut,
    status_code=201,
    summary="Оставить отзыв о товаре",
)
def create_product_review(
    slug: str,
    payload: ReviewIn,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    if not reviews_enabled(db):
        raise HTTPException(status_code=403, detail="Отзывы не подключены в вашем тарифе")
    product = db.scalar(select(Product).where(Product.slug == slug, Product.is_active.is_(True)))
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    phone = payload.phone or (user.phone if user else "")
    if not phone:
        raise HTTPException(status_code=400, detail="Укажите телефон — он нужен только для связи и не публикуется")

    order_id: int | None = None
    verified = False
    order_number = payload.order_number.strip().upper()
    if order_number:
        order = db.scalar(
            select(Order).where(Order.number == order_number, Order.phone == phone)
        )
        if not order:
            raise HTTPException(status_code=400, detail="Заказ с таким номером и телефоном не найден")
        if not any(item.product_id == product.id for item in order.items):
            raise HTTPException(status_code=400, detail="В этом заказе нет выбранного товара")
        order_id = order.id
        verified = True

    review = make_review(
        product_id=product.id,
        customer_name=payload.customer_name,
        phone=phone,
        rating=payload.rating,
        text=payload.text,
        user_id=user.id if user else None,
        order_id=order_id,
        verified=verified,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    audit(
        db,
        action="review.create",
        actor="client",
        user_id=user.id if user else None,
        entity="review",
        entity_id=str(review.id),
        details={"product": product.slug, "rating": review.rating, "verified": verified},
    )
    return review_payload(review)


@router.get("/reviews/latest", response_model=ReviewListOut, summary="Последние отзывы магазина")
def latest_reviews(
    limit: int = Query(default=6, ge=1, le=24),
    db: Session = Depends(get_db),
):
    if not reviews_enabled(db):
        return {"items": [], "total": 0, "average": 0, "distribution": {}, "enabled": False}
    rows = db.scalars(
        select(Review)
        .join(Product, Review.product_id == Product.id)
        .where(Review.status == "published", Product.is_active.is_(True))
        .order_by(Review.published_at.desc(), Review.created_at.desc())
        .limit(limit)
    ).all()
    items = [
        review_payload(row, db.get(Product, row.product_id))
        for row in rows
    ]
    average = db.scalar(
        select(func.avg(Review.rating))
        .join(Product, Review.product_id == Product.id)
        .where(Review.status == "published", Product.is_active.is_(True))
    )
    return {
        "items": items,
        "total": len(items),
        "average": round(float(average or 0), 2),
        "distribution": {},
        "enabled": True,
    }


@router.get("/products/{slug}/related", summary="Похожие товары")
def related_products(slug: str, db: Session = Depends(get_db)):
    product = db.scalar(select(Product).where(Product.slug == slug, Product.is_active.is_(True)))
    if not product:
        return {"items": []}
    tenant = current_tenant()
    if tenant and is_enabled(db, tenant.id, "upsell"):
        items = upsell_service.related(db, product)
        if items:
            return {"items": [product_payload(p) for p in items]}
    stmt = (
        select(Product)
        .where(Product.is_active.is_(True), Product.id != product.id)
        .order_by((Product.category_id == product.category_id).desc(), Product.sort_order.asc())
        .limit(4)
    )
    return {"items": [product_payload(p) for p in db.scalars(stmt).all()]}


@router.get("/chat/thread", summary="Переписка покупателя")
def chat_thread(
    session_key: str = Query(pattern=r"^[A-Za-z0-9_-]{8,64}$"),
    after_id: int = Query(default=0, ge=0),
    read: bool = Query(default=True),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    tenant = current_tenant()
    if tenant and not is_enabled(db, tenant.id, "support_chat"):
        return {"enabled": False, "thread": None, "messages": []}
    result = chat_service.customer_thread(db, session_key, after_id, read)
    db.commit()
    return {"enabled": True, **result}


@router.post("/chat/messages", summary="Отправить сообщение в чат")
def chat_send(
    payload: ChatSendIn,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    tenant = current_tenant()
    if tenant and not is_enabled(db, tenant.id, "support_chat"):
        raise HTTPException(status_code=400, detail="Чат не подключён в вашем тарифе")
    result = chat_service.customer_send(db, payload, user)
    db.commit()
    return result


@router.post("/cart/sync", summary="Сохранить корзину для напоминаний")
def sync_cart(
    payload: CartSyncIn,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    tenant = current_tenant()
    if tenant and not is_enabled(db, tenant.id, "abandoned_cart"):
        return {"stored": False, "enabled": False, "items": 0}
    result = cart_service.sync(db, payload, user)
    db.commit()
    return {"enabled": True, **result}


@router.get("/articles", summary="Полезные статьи о товарах")
def articles(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Product)
        .where(Product.is_active.is_(True), Product.description != "")
        .order_by(Product.sort_order.asc(), Product.title.asc())
    ).all()
    items = []
    for p in rows:
        data = product_payload(p)
        words = len((p.description or "").split())
        items.append(
            {
                "slug": p.slug,
                "title": p.title,
                "subtitle": p.subtitle,
                "image_url": p.image_url,
                "short_description": p.short_description,
                "reading_minutes": max(3, round(words / 150)),
                "category": data["category_title"],
                "season": p.season,
            }
        )
    return {"items": items, "total": len(items)}


@router.get("/promotions", summary="Акции, скидки и товар дня")
def promotions(db: Session = Depends(get_db)):
    rows = db.scalars(select(Product).where(Product.is_active.is_(True))).all()
    daily = next((p for p in rows if p.is_daily_deal), None)
    discounted = [p for p in rows if (p.discount_percent or 0) > 0 and p is not daily]
    discounted.sort(key=lambda p: p.discount_percent, reverse=True)
    conf = get_settings_model(db)
    return {
        "daily_deal": product_payload(daily) if daily else None,
        "discounts": [product_payload(p) for p in discounted[:12]],
        "banners": [b.model_dump() for b in conf.banners if b.is_active],
    }


@router.post("/promo-codes/validate", response_model=PromoValidateOut, summary="Проверить промокод")
def validate_promo(payload: PromoValidateIn, db: Session = Depends(get_db)):
    tenant = current_tenant()
    if tenant:
        from app.platform.sync import is_enabled

        if not is_enabled(db, tenant.id, "promo_codes"):
            raise HTTPException(status_code=400, detail="Промокоды не подключены в вашем тарифе")
    promo, discount, total = resolve_promo(db, payload.code, Decimal(str(payload.subtotal)))
    return {
        "code": promo.code,
        "kind": promo.kind,
        "value": float(promo.value),
        "discount": float(discount),
        "total": float(total),
        "note": promo.note or "",
    }


@router.get("/delivery/zones", response_model=list[DeliveryZoneOut], summary="Зоны доставки")
def delivery_zones(
    subtotal: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
):
    if not delivery_enabled(db):
        return []
    amount = Decimal(str(subtotal)) if subtotal is not None else None
    return [delivery_zone_payload(zone, amount) for zone in delivery_zones_list(db)]


@router.get("/slots", response_model=SlotsOut, summary="Доступное время самовывоза")
def slots(target_date: date = Query(alias="date"), db: Session = Depends(get_db)):
    return get_slots(db, target_date)


@router.post("/orders", response_model=OrderOut, summary="Оформить заказ (с регистрацией или без)")
def make_order(
    payload: OrderCreateIn,
    user: User | None = Depends(get_optional_user),
    x_phone_token: str | None = Header(default=None, alias="X-Phone-Token"),
    db: Session = Depends(get_db),
):
    token = payload.phone_token or x_phone_token
    phone = payload.phone

    if not phone and user:
        phone = user.phone
    if not phone:
        if token:
            phone = phone_from_token(token)
        else:
            raise HTTPException(status_code=400, detail="Укажите номер телефона и подтвердите его кодом из SMS")

    phone = normalize_phone(phone)
    verified = bool(user and user.is_phone_verified and user.phone == phone)
    if not verified:
        if not token:
            raise HTTPException(
                status_code=400,
                detail="Подтвердите номер телефона кодом из SMS — это обязательное требование при оформлении заказа",
            )
        token_data = decode_token(token) or {}
        if token_data.get("purpose") != "order":
            raise HTTPException(
                status_code=400,
                detail="Код подтверждения выдан не для оформления заказа. Запросите новый код.",
            )
        phone_from_token(token, expected_phone=phone)

    order = create_order(db, payload, phone=phone, user=user)
    return order_payload(order)


@router.post("/orders/lookup", response_model=OrderOut, summary="Найти заказ по номеру и телефону")
def lookup_order(payload: OrderLookupIn, db: Session = Depends(get_db)):
    order = db.scalar(select(Order).where(Order.number == payload.number.strip().upper()))
    if not order or order.phone != payload.phone:
        raise HTTPException(status_code=404, detail="Заказ не найден. Проверьте номер заказа и телефон.")
    return order_payload(order)


def public_base_url(request: Request) -> str:
    """База публичных ссылок для текущего магазина."""
    tenant = current_tenant()
    host = request.headers.get("host", "")
    base = str(request.base_url).rstrip("/")
    if tenant and (settings.demo_mode or is_platform_host(host)):
        return f"{base}/shop/{tenant.slug}"
    return base


def build_sitemap(db: Session, base: str, tenant_id: int | None = None, conf=None) -> str:
    conf = conf or get_settings_model(db)
    urls: list[tuple] = [
        (f"{base}/", "1.0", "daily", "home"),
        (f"{base}/catalog", "0.9", "daily", "catalog"),
        (f"{base}/contacts", "0.5", "monthly", "contacts"),
    ]
    if tenant_id is not None:
        from app.platform.sync import is_enabled

        if is_enabled(db, tenant_id, "gift_certificates"):
            urls.append((f"{base}/gift", "0.6", "monthly", "Подарочные сертификаты"))
    category_stmt = select(Category).where(Category.is_active.is_(True))
    product_stmt = select(Product).where(Product.is_active.is_(True))
    if tenant_id is not None:
        category_stmt = category_stmt.where(Category.tenant_id == tenant_id).execution_options(skip_tenant_filter=True)
        product_stmt = product_stmt.where(Product.tenant_id == tenant_id).execution_options(skip_tenant_filter=True)
    categories = db.scalars(
        category_stmt.order_by(Category.sort_order, Category.title)
    ).all()
    for category in categories:
        urls.append((f"{base}/catalog?category={quote(category.slug)}", "0.7", "weekly", category.title))
    products = db.scalars(
        product_stmt.order_by(Product.sort_order, Product.title)
    ).all()
    for product in products:
        lastmod = product.updated_at.date().isoformat() if product.updated_at else ""
        urls.append((f"{base}/fish/{quote(product.slug)}", "0.8", "weekly", product.title, lastmod))

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for item in urls:
        loc, priority, changefreq = item[0], item[1], item[2]
        lastmod = item[4] if len(item) > 4 else ""
        parts.append("<url>")
        parts.append(f"<loc>{xml_escape(loc)}</loc>")
        if lastmod:
            parts.append(f"<lastmod>{lastmod}</lastmod>")
        parts.append(f"<changefreq>{changefreq}</changefreq>")
        parts.append(f"<priority>{priority}</priority>")
        parts.append("</url>")
    parts.append("</urlset>")
    return "".join(parts)


def build_robots(db: Session, base: str, conf=None) -> str:
    conf = conf or get_settings_model(db)
    lines = ["User-agent: *"]
    if conf.seo_indexing:
        lines.extend(
            [
                "Allow: /",
                "Disallow: /admin",
                "Disallow: /platform",
                "Disallow: /seller",
                "Disallow: /account",
                "Disallow: /cart",
                "Disallow: /checkout",
                "Disallow: /lookup",
                f"Sitemap: {base}/sitemap.xml",
            ]
        )
    else:
        lines.append("Disallow: /")
    return "\n".join(lines) + "\n"


@router.get("/seo/sitemap.xml", summary="Карта сайта магазина")
def seo_sitemap(request: Request, db: Session = Depends(get_db)):
    if current_tenant() is None:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    base = public_base_url(request)
    return Response(
        content=build_sitemap(db, base),
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=1800"},
    )


@router.get("/seo/robots.txt", summary="Правила обхода для поисковых систем")
def seo_robots(request: Request, db: Session = Depends(get_db)):
    if current_tenant() is None:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    base = public_base_url(request)
    return Response(
        content=build_robots(db, base),
        media_type="text/plain",
        headers={"Cache-Control": "public, max-age=1800"},
    )


@router.get("/qr/site.png", summary="QR-код на главную страницу")
def qr_site(size: int = Query(default=640, ge=200, le=1200), download: bool = False):
    png = make_qr_png(site_url(), size=size)
    headers = {"Cache-Control": "public, max-age=3600"}
    if download:
        headers["Content-Disposition"] = 'attachment; filename="qr-rybnaya-lavka.png"'
    return Response(content=png, media_type="image/png", headers=headers)


@router.get("/qr/product/{slug}.png", summary="QR-код на статью о товаре")
def qr_product(
    slug: str,
    size: int = Query(default=640, ge=200, le=1200),
    download: bool = False,
    db: Session = Depends(get_db),
):
    product = db.scalar(select(Product).where(Product.slug == slug))
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    png = make_qr_png(product_url(slug), size=size)
    filename = f"qr-{slug}.png"
    disposition = "attachment" if download else "inline"
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": f'{disposition}; filename="{filename}"',
        },
    )
