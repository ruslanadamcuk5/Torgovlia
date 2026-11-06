from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_optional_user, phone_from_token
from app.models import Order, Product, User
from app.schemas import OrderCreateIn, OrderLookupIn, OrderOut, ProductOut, SlotsOut
from app.security import format_phone, normalize_phone
from app.serializers import order_payload, product_payload
from app.services.orders import cancel_by_customer, create_order, get_slots
from app.services.qr import make_qr_png, product_url, site_url
from app.services.settings import get_public_settings, get_settings_model, settings_updated_at
from app.security import decode_token
from app.tenancy import current_tenant
from app.utils import iso, local_today


router = APIRouter(tags=["Публичный сайт"])


@router.get("/site", summary="Настройки сайта, категории и режим работы")
def site_info(db: Session = Depends(get_db)):
    conf = get_settings_model(db)
    tenant = current_tenant()
    categories = db.scalar(select(func.count()).select_from(Product).where(Product.is_active.is_(True))) or 0
    today_hours = next((h for h in conf.working_hours if h.weekday == local_today().weekday()), None)
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
    return {
        "items": [product_payload(p) for p in rows],
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
    return payload


@router.get("/products/{slug}/related", summary="Похожие товары")
def related_products(slug: str, db: Session = Depends(get_db)):
    product = db.scalar(select(Product).where(Product.slug == slug, Product.is_active.is_(True)))
    if not product:
        return {"items": []}
    stmt = (
        select(Product)
        .where(Product.is_active.is_(True), Product.id != product.id)
        .order_by((Product.category_id == product.category_id).desc(), Product.sort_order.asc())
        .limit(4)
    )
    return {"items": [product_payload(p) for p in db.scalars(stmt).all()]}


@router.get("/articles", summary="Полезные статьи о рыбе")
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


@router.get("/slots", response_model=SlotsOut, summary="Доступное время самовывоза")
def slots(target_date: date = Query(alias="date"), db: Session = Depends(get_db)):
    return get_slots(db, target_date)


@router.post("/orders", response_model=OrderOut, summary="Оформить бронь (с регистрацией или без)")
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
                detail="Подтвердите номер телефона кодом из SMS — это обязательное требование при оформлении брони",
            )
        token_data = decode_token(token) or {}
        if token_data.get("purpose") != "order":
            raise HTTPException(
                status_code=400,
                detail="Код подтверждения выдан не для оформления брони. Запросите новый код.",
            )
        phone_from_token(token, expected_phone=phone)

    order = create_order(db, payload, phone=phone, user=user)
    return order_payload(order)


@router.post("/orders/lookup", response_model=OrderOut, summary="Найти бронь по номеру и телефону")
def lookup_order(payload: OrderLookupIn, db: Session = Depends(get_db)):
    order = db.scalar(select(Order).where(Order.number == payload.number.strip().upper()))
    if not order or order.phone != payload.phone:
        raise HTTPException(status_code=404, detail="Бронь не найдена. Проверьте номер заказа и телефон.")
    return order_payload(order)


@router.get("/qr/site.png", summary="QR-код на главную страницу")
def qr_site(size: int = Query(default=640, ge=200, le=1200), download: bool = False):
    png = make_qr_png(site_url(), size=size)
    headers = {"Cache-Control": "public, max-age=3600"}
    if download:
        headers["Content-Disposition"] = 'attachment; filename="qr-rybnaya-lavka.png"'
    return Response(content=png, media_type="image/png", headers=headers)


@router.get("/qr/product/{slug}.png", summary="QR-код на статью о рыбе")
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
