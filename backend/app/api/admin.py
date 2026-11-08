import csv
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import (
    REVIEW_STATUSES,
    ROLE_ADMIN,
    ROLE_CUSTOMER,
    ROLE_SELLER,
    ORDER_CANCELLED,
    ORDER_COMPLETED,
    ORDER_REJECTED,
    AuditLog,
    Category,
    DeliveryZone,
    Order,
    OrderItem,
    Product,
    PromoCode,
    PurchaseOrder,
    Review,
    StockMovement,
    Supplier,
    User,
)
from app.schemas import (
    ActiveIn,
    AdminUserCreate,
    AdminUserUpdate,
    CategoryIn,
    DeliveryZoneIn,
    DeliveryZoneOut,
    NotificationSettingsIn,
    NotificationTestIn,
    OrderOut,
    OrderStatusIn,
    ProductIn,
    ProductOut,
    ProductPatch,
    PromoCodeIn,
    PromoCodeOut,
    PurchaseIn,
    PurchasePatch,
    ReviewModerationIn,
    ReviewOut,
    RoleIn,
    SiteSettings,
    SiteSettingsOut,
    StockMoveIn,
    SupplierIn,
    SupplierPatch,
    OnboardingOut,
    StatsOut,
    UploadOut,
    UserAdminOut,
)
from app.security import format_phone, hash_password, validate_password
from app.serializers import order_payload, product_admin_payload, product_payload
from app.services.audit import audit
from app.services import barcode as barcode_service
from app.services.delivery import serialize as delivery_zone_payload
from app.services.onboarding import payload as onboarding_payload
from app.services.orders import transition_order
from app.services.notifications import channels_status, test_channel
from app.services.inventory import apply_move, serialize as movement_payload
from app.services.purchases import (
    create_purchase,
    serialize_purchase,
    serialize_supplier,
    transition_purchase,
)
from app.services.promotions import find_promo, normalize_code, serialize as promo_payload
from app.services.reviews import admin_payload as review_admin_payload, moderate as moderate_review
from app.services.qr import product_url, site_url
from app.services.settings import get_settings_model, save_settings, settings_updated_at
from app.services.storage import save_image
from app.tenancy import current_tenant, tenant_get
from app.utils import local_now, local_today, money, slugify


router = APIRouter(prefix="/admin", tags=["Администрирование"])


def _unique_slug(db: Session, title: str, exclude_id: int | None = None) -> str:
    base = slugify(title, fallback="tovar")
    slug = base
    index = 2
    while True:
        stmt = select(Product.id).where(Product.slug == slug)
        if exclude_id:
            stmt = stmt.where(Product.id != exclude_id)
        if not db.scalar(stmt):
            return slug
        slug = f"{base}-{index}"
        index += 1


# ─────────────────────────── Дашборд ───────────────────────────

@router.get("/stats", response_model=StatsOut, summary="Сводка по магазину")
def stats(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    today = local_today()
    month_start = today.replace(day=1)
    active_statuses = ("confirmed", "ready", "completed")

    orders_total = db.scalar(select(func.count(Order.id))) or 0
    orders_new = db.scalar(select(func.count(Order.id)).where(Order.status == "new")) or 0
    orders_today = db.scalar(select(func.count(Order.id)).where(Order.pickup_date == today)) or 0
    revenue_today = db.scalar(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.status == "completed", Order.pickup_date == today
        )
    ) or 0
    revenue_month = db.scalar(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.status == "completed", Order.pickup_date >= month_start
        )
    ) or 0
    users_total = db.scalar(select(func.count(User.id))) or 0
    customers_total = db.scalar(select(func.count(User.id)).where(User.role == ROLE_CUSTOMER)) or 0
    products_active = db.scalar(select(func.count(Product.id)).where(Product.is_active.is_(True))) or 0
    out_of_stock = db.scalar(
        select(func.count(Product.id)).where(Product.is_active.is_(True), Product.is_available.is_(False))
    ) or 0
    avg_order = db.scalar(
        select(func.coalesce(func.avg(Order.total_amount), 0)).where(Order.status.in_(("confirmed", "ready", "completed")))
    ) or 0

    top = db.execute(
        select(OrderItem.title, func.sum(OrderItem.quantity), func.sum(OrderItem.line_total))
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status.in_(active_statuses))
        .group_by(OrderItem.title)
        .order_by(func.sum(OrderItem.line_total).desc())
        .limit(5)
    ).all()

    return {
        "orders_total": int(orders_total),
        "orders_new": int(orders_new),
        "orders_today": int(orders_today),
        "revenue_month": float(money(revenue_month)),
        "revenue_today": float(money(revenue_today)),
        "users_total": int(users_total),
        "customers_total": int(customers_total),
        "products_active": int(products_active),
        "products_out_of_stock": int(out_of_stock),
        "avg_order": float(money(avg_order)),
        "top_products": [
            {"title": row[0], "quantity": float(row[1]), "revenue": float(money(row[2]))} for row in top
        ],
    }


@router.get(
    "/onboarding",
    response_model=OnboardingOut,
    summary="Чек-лист запуска магазина",
)
def onboarding(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return onboarding_payload(db)


# ─────────────────────────── Промокоды ───────────────────────────

def _require_promo_service(db: Session) -> None:
    tenant = current_tenant()
    if tenant:
        from app.platform.sync import is_enabled

        if not is_enabled(db, tenant.id, "promo_codes"):
            raise HTTPException(
                status_code=403,
                detail="Промокоды доступны на тарифе «Бизнес» и выше",
            )


@router.get("/promo-codes", response_model=list[PromoCodeOut], summary="Промокоды магазина")
def list_promo_codes(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    _require_promo_service(db)
    rows = db.scalars(select(PromoCode).order_by(PromoCode.created_at.desc())).all()
    return [promo_payload(row) for row in rows]


@router.post("/promo-codes", response_model=PromoCodeOut, status_code=201, summary="Создать промокод")
def create_promo_code(
    payload: PromoCodeIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _require_promo_service(db)
    code = normalize_code(payload.code)
    if find_promo(db, code):
        raise HTTPException(status_code=409, detail="Такой промокод уже есть")
    promo = PromoCode(
        code=code,
        kind=payload.kind,
        value=Decimal(str(payload.value)),
        min_order=Decimal(str(payload.min_order)),
        max_uses=payload.max_uses,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        is_active=payload.is_active,
        note=payload.note.strip(),
    )
    db.add(promo)
    db.commit()
    db.refresh(promo)
    audit(
        db,
        action="promo_code.create",
        actor=user.phone,
        user_id=user.id,
        entity="promo_code",
        entity_id=promo.code,
        details={"kind": promo.kind, "value": float(promo.value)},
    )
    return promo_payload(promo)


@router.put("/promo-codes/{promo_id}", response_model=PromoCodeOut, summary="Изменить промокод")
def update_promo_code(
    promo_id: int,
    payload: PromoCodeIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _require_promo_service(db)
    promo = tenant_get(db, PromoCode, promo_id)
    if not promo:
        raise HTTPException(status_code=404, detail="Промокод не найден")
    code = normalize_code(payload.code)
    duplicate = find_promo(db, code)
    if duplicate and duplicate.id != promo.id:
        raise HTTPException(status_code=409, detail="Такой промокод уже есть")
    promo.code = code
    promo.kind = payload.kind
    promo.value = Decimal(str(payload.value))
    promo.min_order = Decimal(str(payload.min_order))
    promo.max_uses = payload.max_uses
    promo.starts_at = payload.starts_at
    promo.ends_at = payload.ends_at
    promo.is_active = payload.is_active
    promo.note = payload.note.strip()
    db.commit()
    db.refresh(promo)
    audit(
        db,
        action="promo_code.update",
        actor=user.phone,
        user_id=user.id,
        entity="promo_code",
        entity_id=promo.code,
        details={"active": promo.is_active},
    )
    return promo_payload(promo)


@router.delete("/promo-codes/{promo_id}", status_code=204, summary="Удалить промокод")
def delete_promo_code(
    promo_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _require_promo_service(db)
    promo = tenant_get(db, PromoCode, promo_id)
    if not promo:
        raise HTTPException(status_code=404, detail="Промокод не найден")
    if promo.used_count:
        raise HTTPException(
            status_code=409,
            detail="Промокод уже использовали — отключите его вместо удаления",
        )
    code = promo.code
    db.delete(promo)
    db.commit()
    audit(
        db,
        action="promo_code.delete",
        actor=user.phone,
        user_id=user.id,
        entity="promo_code",
        entity_id=code,
    )
    return Response(status_code=204)


# ─────────────────────────── Отзывы ───────────────────────────

def _require_review_service(db: Session) -> None:
    tenant = current_tenant()
    if tenant:
        from app.platform.sync import is_enabled

        if not is_enabled(db, tenant.id, "reviews"):
            raise HTTPException(
                status_code=403,
                detail="Отзывы доступны на тарифе «Бизнес» и выше",
            )


@router.get("/reviews", response_model=list[ReviewOut], summary="Отзывы магазина")
def list_reviews(
    status_filter: str | None = Query(default=None, alias="status"),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _require_review_service(db)
    stmt = select(Review).order_by(Review.created_at.desc()).limit(200)
    if status_filter:
        if status_filter not in REVIEW_STATUSES:
            raise HTTPException(status_code=400, detail="Неизвестный статус отзыва")
        stmt = stmt.where(Review.status == status_filter)
    rows = db.scalars(stmt).all()
    return [review_admin_payload(row, db.get(Product, row.product_id)) for row in rows]


@router.patch("/reviews/{review_id}", response_model=ReviewOut, summary="Опубликовать или отклонить отзыв")
def moderate_product_review(
    review_id: int,
    payload: ReviewModerationIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _require_review_service(db)
    review = tenant_get(db, Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Отзыв не найден")
    moderate_review(review, payload.status, payload.admin_comment)
    db.commit()
    db.refresh(review)
    audit(
        db,
        action="review.moderate",
        actor=user.phone,
        user_id=user.id,
        entity="review",
        entity_id=str(review.id),
        details={"status": review.status},
    )
    return review_admin_payload(review, db.get(Product, review.product_id))


@router.delete("/reviews/{review_id}", status_code=204, summary="Удалить отзыв")
def delete_product_review(
    review_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _require_review_service(db)
    review = tenant_get(db, Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Отзыв не найден")
    product_slug = db.get(Product, review.product_id)
    db.delete(review)
    db.commit()
    audit(
        db,
        action="review.delete",
        actor=user.phone,
        user_id=user.id,
        entity="review",
        entity_id=str(review_id),
        details={"product": product_slug.slug if product_slug else ""},
    )
    return Response(status_code=204)


# ─────────────────────────── Доставка ───────────────────────────

def _require_delivery_service(db: Session) -> None:
    tenant = current_tenant()
    if tenant:
        from app.platform.sync import is_enabled

        if not is_enabled(db, tenant.id, "delivery"):
            raise HTTPException(
                status_code=403,
                detail="Доставка доступна на тарифе «Бизнес» и выше",
            )


@router.get("/delivery/zones", response_model=list[DeliveryZoneOut], summary="Зоны доставки")
def list_delivery_zones(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _require_delivery_service(db)
    rows = db.scalars(
        select(DeliveryZone).order_by(DeliveryZone.sort_order.asc(), DeliveryZone.name.asc())
    ).all()
    return [delivery_zone_payload(row) for row in rows]


@router.post("/delivery/zones", response_model=DeliveryZoneOut, status_code=201, summary="Создать зону доставки")
def create_delivery_zone(
    payload: DeliveryZoneIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _require_delivery_service(db)
    zone = DeliveryZone(
        name=payload.name.strip(),
        areas=payload.areas.strip(),
        fee=Decimal(str(payload.fee)),
        min_order=Decimal(str(payload.min_order)),
        free_from=Decimal(str(payload.free_from)),
        eta=payload.eta.strip(),
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    audit(
        db,
        action="delivery_zone.create",
        actor=user.phone,
        user_id=user.id,
        entity="delivery_zone",
        entity_id=str(zone.id),
        details={"name": zone.name, "fee": float(zone.fee)},
    )
    return delivery_zone_payload(zone)


@router.put("/delivery/zones/{zone_id}", response_model=DeliveryZoneOut, summary="Изменить зону доставки")
def update_delivery_zone(
    zone_id: int,
    payload: DeliveryZoneIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _require_delivery_service(db)
    zone = tenant_get(db, DeliveryZone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Зона доставки не найдена")
    zone.name = payload.name.strip()
    zone.areas = payload.areas.strip()
    zone.fee = Decimal(str(payload.fee))
    zone.min_order = Decimal(str(payload.min_order))
    zone.free_from = Decimal(str(payload.free_from))
    zone.eta = payload.eta.strip()
    zone.is_active = payload.is_active
    zone.sort_order = payload.sort_order
    db.commit()
    db.refresh(zone)
    audit(
        db,
        action="delivery_zone.update",
        actor=user.phone,
        user_id=user.id,
        entity="delivery_zone",
        entity_id=str(zone.id),
        details={"name": zone.name, "active": zone.is_active},
    )
    return delivery_zone_payload(zone)


@router.delete("/delivery/zones/{zone_id}", status_code=204, summary="Удалить зону доставки")
def delete_delivery_zone(
    zone_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _require_delivery_service(db)
    zone = tenant_get(db, DeliveryZone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Зона доставки не найдена")
    name = zone.name
    db.delete(zone)
    db.commit()
    audit(
        db,
        action="delivery_zone.delete",
        actor=user.phone,
        user_id=user.id,
        entity="delivery_zone",
        entity_id=str(zone_id),
        details={"name": name},
    )
    return Response(status_code=204)


# ─────────────────────────── Настройки ───────────────────────────

@router.get("/settings", response_model=SiteSettingsOut, summary="Получить настройки сайта")
def read_settings(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {"settings": get_settings_model(db), "updated_at": settings_updated_at(db)}


@router.put("/settings", response_model=SiteSettingsOut, summary="Сохранить настройки сайта")
def update_settings(
    payload: SiteSettings,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    saved = save_settings(db, payload)
    audit(db, "settings.update", actor=user.phone, user_id=user.id, entity="settings", entity_id="1")
    db.commit()
    return {"settings": saved, "updated_at": settings_updated_at(db)}


@router.get("/notifications", summary="Настройки уведомлений магазина")
def read_notifications(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    conf = get_settings_model(db)
    return {
        "settings": {
            "notify_on_new_order": conf.notify_on_new_order,
            "notify_on_cancel": conf.notify_on_cancel,
            "notify_telegram_chat": conf.notify_telegram_chat,
            "notify_sms_phone": conf.notify_sms_phone,
            "notify_email": conf.notify_email,
        },
        "channels": channels_status(),
    }


@router.put("/notifications", summary="Сохранить настройки уведомлений")
def update_notifications(
    payload: NotificationSettingsIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    current = get_settings_model(db)
    data = current.model_dump()
    data.update(payload.model_dump())
    saved = save_settings(db, SiteSettings.model_validate(data))
    audit(db, "notifications.update", actor=user.phone, user_id=user.id, entity="settings", entity_id="1")
    db.commit()
    return {
        "settings": {
            "notify_on_new_order": saved.notify_on_new_order,
            "notify_on_cancel": saved.notify_on_cancel,
            "notify_telegram_chat": saved.notify_telegram_chat,
            "notify_sms_phone": saved.notify_sms_phone,
            "notify_email": saved.notify_email,
        },
        "channels": channels_status(),
    }


@router.post("/notifications/test", summary="Отправить тестовое уведомление")
def send_test_notification(
    payload: NotificationTestIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    conf = get_settings_model(db)
    target = payload.target.strip()
    if not target:
        target = {
            "telegram": conf.notify_telegram_chat,
            "sms": conf.notify_sms_phone,
            "email": conf.notify_email,
        }[payload.channel].strip()
    if not target:
        raise HTTPException(status_code=400, detail="Укажите адрес доставки уведомления")

    from app.services.sms import SmsError

    try:
        test_channel(payload.channel, target)
    except (RuntimeError, SmsError, ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)[:300]) from exc
    audit(
        db,
        "notifications.test",
        actor=user.phone,
        user_id=user.id,
        entity="settings",
        entity_id="1",
        details={"channel": payload.channel},
    )
    db.commit()
    return {"sent": True, "channel": payload.channel}


# ─────────────────────────── Каталог ───────────────────────────

@router.get("/products", summary="Все товары, включая скрытые")
def admin_products(
    q: str | None = None,
    category_id: int | None = None,
    include_inactive: bool = True,
    limit: int = Query(default=300, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(Product)
    count_stmt = select(func.count(Product.id))
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
        count_stmt = count_stmt.where(Product.is_active.is_(True))
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
        count_stmt = count_stmt.where(Product.category_id == category_id)
    if q:
        pattern = f"%{q.strip()}%"
        clause = or_(Product.title.ilike(pattern), Product.slug.ilike(pattern))
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)
    rows = db.scalars(stmt.order_by(Product.is_active.desc(), Product.sort_order, Product.title).offset(offset).limit(limit)).unique().all()
    return {
        "items": [product_admin_payload(p) for p in rows],
        "total": int(db.scalar(count_stmt) or 0),
        "limit": limit,
        "offset": offset,
    }


@router.get("/barcodes/lookup", summary="Найти товар по штрихкоду")
def lookup_barcode(
    code: str = Query(min_length=1, max_length=64),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = barcode_service.lookup(db, code)
    if not product:
        raise HTTPException(status_code=404, detail="Товар со штрихкодом не найден")
    return barcode_service.label_payload(product)


@router.post("/barcodes/backfill", summary="Создать штрихкоды всем товарам")
def backfill_product_barcodes(
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    updated = barcode_service.backfill(db)
    audit(
        db,
        "barcode.backfill",
        actor=user.phone,
        user_id=user.id,
        entity="product",
        entity_id="all",
        details={"updated": updated},
    )
    db.commit()
    return {"updated": updated}


@router.post("/products/{product_id}/barcode", response_model=ProductOut, summary="Создать или обновить штрихкод товара")
def refresh_product_barcode(
    product_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = tenant_get(db, Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    barcode_service.assign(db, product)
    audit(
        db,
        "barcode.generate",
        actor=user.phone,
        user_id=user.id,
        entity="product",
        entity_id=str(product.id),
        details={"barcode": product.barcode},
    )
    db.commit()
    db.refresh(product)
    return product_admin_payload(product)


@router.get("/products/{product_id}", response_model=ProductOut, summary="Товар для редактирования")
def admin_product(product_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    product = tenant_get(db, Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return product_admin_payload(product)


@router.post("/products", response_model=ProductOut, summary="Создать товар")
def create_product(payload: ProductIn, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    slug = payload.slug.strip() if payload.slug else _unique_slug(db, payload.title)
    if db.scalar(select(Product.id).where(Product.slug == slug)):
        raise HTTPException(status_code=400, detail="Такой адрес (slug) уже занят")
    product = Product(
        slug=slug,
        title=payload.title.strip(),
        subtitle=payload.subtitle,
        category_id=payload.category_id,
        unit=payload.unit,
        price=money(payload.price),
        discount_percent=payload.discount_percent,
        is_daily_deal=payload.is_daily_deal,
        is_available=payload.is_available,
        is_active=payload.is_active,
        stock=payload.stock,
        weight_note=payload.weight_note,
        image_url=payload.image_url,
        gallery=payload.gallery,
        badges=payload.badges,
        short_description=payload.short_description,
        description=payload.description,
        origin=payload.origin,
        season=payload.season,
        nutrition=payload.nutrition,
        cooking_tips=payload.cooking_tips,
        storage_tips=payload.storage_tips,
        sort_order=payload.sort_order,
    )
    db.add(product)
    db.flush()
    if payload.barcode:
        barcode_service.assign(db, product, payload.barcode)
    else:
        barcode_service.assign_default(db, product)
    audit(db, "product.create", actor=user.phone, user_id=user.id, entity="product", entity_id=product.id,
          details={"title": product.title})
    db.commit()
    db.refresh(product)
    return product_admin_payload(product)


@router.patch("/products/{product_id}", response_model=ProductOut, summary="Изменить товар")
def update_product(
    product_id: int,
    payload: ProductPatch,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = tenant_get(db, Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    data = payload.model_dump(exclude_unset=True)
    barcode_value = data.pop("barcode", None)
    if "slug" in data and data["slug"]:
        slug = data["slug"].strip()
        if db.scalar(select(Product.id).where(Product.slug == slug, Product.id != product_id)):
            raise HTTPException(status_code=400, detail="Такой адрес (slug) уже занят")
        data["slug"] = slug
    if "price" in data and data["price"] is not None:
        data["price"] = money(data["price"])
    for key, value in data.items():
        setattr(product, key, value)
    if barcode_value:
        barcode_service.assign(db, product, barcode_value)
    audit(db, "product.update", actor=user.phone, user_id=user.id, entity="product", entity_id=product.id,
          details={"fields": list(data.keys())})
    db.commit()
    db.refresh(product)
    return product_admin_payload(product)


@router.delete("/products/{product_id}", summary="Снять товар с продажи")
def delete_product(
    product_id: int,
    hard: bool = False,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = tenant_get(db, Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    used = db.scalar(select(func.count(OrderItem.id)).where(OrderItem.product_id == product_id)) or 0
    if hard and used == 0:
        db.delete(product)
        action = "product.delete"
    else:
        product.is_active = False
        product.is_available = False
        action = "product.deactivate"
    audit(db, action, actor=user.phone, user_id=user.id, entity="product", entity_id=product_id)
    db.commit()
    return {"ok": True, "message": "Товар скрыт из каталога" if not hard or used else "Товар удалён"}


# ─────────────────────────── Категории ───────────────────────────

@router.get("/categories", summary="Категории")
def admin_categories(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    counts = dict(
        db.execute(select(Product.category_id, func.count(Product.id)).group_by(Product.category_id)).all()
    )
    rows = db.scalars(select(Category).order_by(Category.sort_order, Category.title)).all()
    return {
        "items": [
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
    }


@router.post("/categories", summary="Создать категорию")
def create_category(payload: CategoryIn, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    slug = (payload.slug or slugify(payload.title, "category")).strip()
    if db.scalar(select(Category.id).where(Category.slug == slug)):
        raise HTTPException(status_code=400, detail="Категория с таким адресом уже существует")
    category = Category(
        slug=slug,
        title=payload.title.strip(),
        description=payload.description,
        image_url=payload.image_url,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(category)
    db.flush()
    audit(db, "category.create", actor=user.phone, user_id=user.id, entity="category", entity_id=category.id)
    db.commit()
    return {"id": category.id, "slug": category.slug, "title": category.title}


@router.patch("/categories/{category_id}", summary="Изменить категорию")
def update_category(
    category_id: int,
    payload: CategoryIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    category = tenant_get(db, Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    category.title = payload.title.strip()
    category.description = payload.description
    category.image_url = payload.image_url
    category.sort_order = payload.sort_order
    category.is_active = payload.is_active
    audit(db, "category.update", actor=user.phone, user_id=user.id, entity="category", entity_id=category.id)
    db.commit()
    return {"ok": True}


@router.delete("/categories/{category_id}", summary="Удалить категорию")
def delete_category(category_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    category = tenant_get(db, Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    in_use = db.scalar(select(func.count(Product.id)).where(Product.category_id == category_id)) or 0
    if in_use:
        raise HTTPException(status_code=400, detail="В категории есть товары. Сначала перенесите их.")
    db.delete(category)
    audit(db, "category.delete", actor=user.phone, user_id=user.id, entity="category", entity_id=category_id)
    db.commit()
    return {"ok": True}


# ─────────────────────────── Заказы ───────────────────────────

@router.get("/orders", summary="Брони с фильтрами")
def admin_orders(
    status: str | None = None,
    pickup_date: date | None = None,
    q: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(Order)
    count_stmt = select(func.count(Order.id))
    if status and status != "all":
        if status == "active":
            stmt = stmt.where(Order.status.in_(("new", "confirmed", "ready")))
            count_stmt = count_stmt.where(Order.status.in_(("new", "confirmed", "ready")))
        else:
            stmt = stmt.where(Order.status == status)
            count_stmt = count_stmt.where(Order.status == status)
    if pickup_date:
        stmt = stmt.where(Order.pickup_date == pickup_date)
        count_stmt = count_stmt.where(Order.pickup_date == pickup_date)
    if q:
        pattern = f"%{q.strip()}%"
        clause = or_(Order.number.ilike(pattern), Order.phone.ilike(pattern), Order.customer_name.ilike(pattern))
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)
    rows = db.scalars(stmt.order_by(Order.created_at.desc()).offset(offset).limit(limit)).unique().all()
    return {
        "items": [order_payload(o) for o in rows],
        "total": int(db.scalar(count_stmt) or 0),
        "limit": limit,
        "offset": offset,
    }


# ─────────────────────────── Поставщики и закупки ───────────────────────────

@router.get("/suppliers", summary="Поставщики магазина")
def list_suppliers(
    q: str | None = None,
    active_only: bool = False,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(Supplier)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Supplier.name.ilike(pattern),
                Supplier.contact_person.ilike(pattern),
                Supplier.phone.ilike(pattern),
                Supplier.email.ilike(pattern),
            )
        )
    if active_only:
        stmt = stmt.where(Supplier.is_active.is_(True))
    rows = db.scalars(stmt.order_by(Supplier.is_active.desc(), Supplier.name)).all()

    counts = {
        row[0]: int(row[1])
        for row in db.execute(
            select(PurchaseOrder.supplier_id, func.count(PurchaseOrder.id))
            .where(PurchaseOrder.supplier_id.is_not(None))
            .group_by(PurchaseOrder.supplier_id)
        ).all()
    }
    items = []
    for supplier in rows:
        payload = serialize_supplier(supplier)
        payload["purchases_count"] = counts.get(supplier.id, 0)
        items.append(payload)
    return {"items": items, "total": len(items)}


@router.post("/suppliers", status_code=201, summary="Добавить поставщика")
def create_supplier(
    payload: SupplierIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    supplier = Supplier(**payload.model_dump())
    supplier.name = supplier.name.strip()
    supplier.contact_person = supplier.contact_person.strip()
    supplier.phone = supplier.phone.strip()
    supplier.email = supplier.email.strip()
    supplier.address = supplier.address.strip()
    supplier.note = supplier.note.strip()
    db.add(supplier)
    db.flush()
    audit(
        db,
        "supplier.create",
        actor=user.phone,
        user_id=user.id,
        entity="supplier",
        entity_id=str(supplier.id),
        details={"name": supplier.name},
    )
    db.commit()
    db.refresh(supplier)
    return serialize_supplier(supplier)


@router.patch("/suppliers/{supplier_id}", summary="Изменить поставщика")
def update_supplier(
    supplier_id: int,
    payload: SupplierPatch,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    supplier = tenant_get(db, Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(supplier, key, value)
    audit(
        db,
        "supplier.update",
        actor=user.phone,
        user_id=user.id,
        entity="supplier",
        entity_id=str(supplier.id),
        details={"fields": sorted(data)},
    )
    db.commit()
    db.refresh(supplier)
    return serialize_supplier(supplier)


@router.delete("/suppliers/{supplier_id}", status_code=204, summary="Удалить поставщика")
def delete_supplier(
    supplier_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    supplier = tenant_get(db, Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    audit(
        db,
        "supplier.delete",
        actor=user.phone,
        user_id=user.id,
        entity="supplier",
        entity_id=str(supplier.id),
        details={"name": supplier.name},
    )
    db.delete(supplier)
    db.commit()
    return Response(status_code=204)


@router.get("/purchases", summary="Закупки у поставщиков")
def list_purchases(
    status: str | None = None,
    supplier_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()).limit(limit)
    if status and status != "all":
        stmt = stmt.where(PurchaseOrder.status == status)
    if supplier_id:
        stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
    rows = db.scalars(stmt).unique().all()
    return {"items": [serialize_purchase(row) for row in rows], "total": len(rows)}


@router.post("/purchases", status_code=201, summary="Создать закупку")
def add_purchase(
    payload: PurchaseIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    purchase = create_purchase(db, payload)
    audit(
        db,
        "purchase.create",
        actor=user.phone,
        user_id=user.id,
        entity="purchase",
        entity_id=str(purchase.id),
        details={"number": purchase.number, "total": float(purchase.total_amount)},
    )
    db.commit()
    db.refresh(purchase)
    return serialize_purchase(purchase)


@router.get("/purchases/{purchase_id}", summary="Детали закупки")
def purchase_details(
    purchase_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    purchase = tenant_get(db, PurchaseOrder, purchase_id)
    if not purchase:
        raise HTTPException(status_code=404, detail="Закупка не найдена")
    return serialize_purchase(purchase)


@router.patch("/purchases/{purchase_id}", summary="Изменить закупку или принять товар")
def update_purchase(
    purchase_id: int,
    payload: PurchasePatch,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    purchase = tenant_get(db, PurchaseOrder, purchase_id)
    if not purchase:
        raise HTTPException(status_code=404, detail="Закупка не найдена")
    data = payload.model_dump(exclude_unset=True)
    if data.get("expected_date") is not None:
        purchase.expected_date = data["expected_date"]
    if data.get("note") is not None:
        purchase.note = data["note"].strip()
    status = data.get("status")
    if status:
        purchase = transition_purchase(db, purchase, status, user.phone)
        audit(
            db,
            f"purchase.{status}",
            actor=user.phone,
            user_id=user.id,
            entity="purchase",
            entity_id=str(purchase.id),
            details={"number": purchase.number},
        )
    db.commit()
    db.refresh(purchase)
    return serialize_purchase(purchase)


@router.delete("/purchases/{purchase_id}", status_code=204, summary="Удалить черновик закупки")
def delete_purchase(
    purchase_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    purchase = tenant_get(db, PurchaseOrder, purchase_id)
    if not purchase:
        raise HTTPException(status_code=404, detail="Закупка не найдена")
    if purchase.status not in ("draft", "cancelled"):
        raise HTTPException(status_code=400, detail="Удалить можно только черновик или отменённую закупку")
    audit(
        db,
        "purchase.delete",
        actor=user.phone,
        user_id=user.id,
        entity="purchase",
        entity_id=str(purchase.id),
        details={"number": purchase.number},
    )
    db.delete(purchase)
    db.commit()
    return Response(status_code=204)


# ─────────────────────────── Склад ───────────────────────────

@router.get("/inventory", summary="Остатки товаров и предупреждения")
def inventory(
    q: str | None = None,
    low_only: bool = False,
    threshold: float = Query(default=5, ge=0, le=100000),
    limit: int = Query(default=500, ge=1, le=1000),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(Product).where(Product.is_active.is_(True))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(Product.title.ilike(pattern), Product.slug.ilike(pattern)))
    products = db.scalars(stmt.order_by(Product.title).limit(limit)).unique().all()

    items = []
    tracked = low = out = 0
    for product in products:
        stock = float(product.stock) if product.stock is not None else None
        is_out = stock is not None and stock <= 0
        is_low = stock is not None and 0 < stock <= threshold
        if stock is not None:
            tracked += 1
            if is_out:
                out += 1
            elif is_low:
                low += 1
        if low_only and not (is_low or is_out):
            continue
        items.append(
            {
                "id": product.id,
                "title": product.title,
                "slug": product.slug,
                "unit": product.unit,
                "category_title": product.category.title if product.category else None,
                "stock": stock,
                "price": float(product.price or 0),
                "is_available": bool(product.is_available),
                "is_out": is_out,
                "is_low": is_low,
            }
        )
    items.sort(key=lambda item: (item["stock"] is None, item["stock"] if item["stock"] is not None else 0))
    return {
        "items": items,
        "total": len(items),
        "summary": {"tracked": tracked, "low": low, "out": out, "threshold": threshold},
    }


@router.get("/inventory/movements", summary="История движения остатков")
def inventory_movements(
    product_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(StockMovement).order_by(StockMovement.created_at.desc()).limit(limit)
    if product_id:
        stmt = stmt.where(StockMovement.product_id == product_id)
    rows = db.scalars(stmt).all()
    return {"items": [movement_payload(row) for row in rows], "total": len(rows)}


@router.post("/inventory/{product_id}/movement", summary="Приход, списание или инвентаризация")
def inventory_move(
    product_id: int,
    payload: StockMoveIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = tenant_get(db, Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    movement = apply_move(
        db,
        product,
        kind=payload.kind,
        quantity=payload.quantity,
        reason=payload.reason,
        actor=user.phone,
    )
    audit(
        db,
        f"inventory.{payload.kind}",
        actor=user.phone,
        user_id=user.id,
        entity="product",
        entity_id=str(product.id),
        details={"quantity": payload.quantity, "stock_after": float(product.stock or 0)},
    )
    db.commit()
    db.refresh(movement)
    return {
        "movement": movement_payload(movement),
        "stock": float(product.stock or 0),
    }


STATUS_LABELS = {
    "new": "Новая",
    "confirmed": "Подтверждена",
    "ready": "Готова",
    "completed": "Выдана",
    "cancelled": "Отменена",
    "rejected": "Отклонена",
}


def _report_range(days: int) -> tuple[date, date]:
    today = local_today()
    return today - timedelta(days=max(1, days) - 1), today


def build_report(db: Session, date_from: date, date_to: date) -> dict:
    orders = db.scalars(
        select(Order)
        .where(Order.pickup_date >= date_from, Order.pickup_date <= date_to)
        .order_by(Order.pickup_date)
    ).unique().all()

    daily = {
        date_from + timedelta(days=index): {"date": (date_from + timedelta(days=index)).isoformat(), "orders": 0, "completed": 0, "revenue": 0.0}
        for index in range((date_to - date_from).days + 1)
    }
    statuses = {code: 0 for code in STATUS_LABELS}
    top: dict[str, dict] = {}
    categories: dict[str, float] = {}
    fulfillment = {"pickup": 0, "delivery": 0}
    revenue = discount = delivery_fee = items_sold = 0.0
    completed = 0
    period_phones: set[str] = set()

    product_ids = {item.product_id for order in orders for item in order.items if item.product_id}
    product_categories: dict[int, int | None] = {}
    category_titles: dict[int, str] = {}
    if product_ids:
        for product in db.scalars(select(Product).where(Product.id.in_(product_ids))).all():
            product_categories[product.id] = product.category_id
        category_ids = {value for value in product_categories.values() if value}
        if category_ids:
            for category in db.scalars(select(Category).where(Category.id.in_(category_ids))).all():
                category_titles[category.id] = category.title

    for order in orders:
        day = daily.get(order.pickup_date)
        if day:
            day["orders"] += 1
        statuses[order.status] = statuses.get(order.status, 0) + 1
        period_phones.add(order.phone)
        fulfillment["delivery" if order.fulfillment == "delivery" else "pickup"] += 1
        if order.status != ORDER_COMPLETED:
            continue

        completed += 1
        amount = float(order.total_amount)
        revenue += amount
        discount += float(order.discount_amount)
        delivery_fee += float(order.delivery_fee)
        if day:
            day["completed"] += 1
            day["revenue"] = round(day["revenue"] + amount, 2)
        for item in order.items:
            quantity = float(item.quantity)
            line = float(item.line_total)
            items_sold += quantity
            bucket = top.setdefault(item.title, {"title": item.title, "quantity": 0.0, "revenue": 0.0})
            bucket["quantity"] += quantity
            bucket["revenue"] += line
            category_id = product_categories.get(item.product_id) if item.product_id else None
            if category_id and category_id in category_titles:
                title = category_titles[category_id]
                categories[title] = categories.get(title, 0.0) + line

    earlier_phones: set[str] = set()
    if period_phones:
        earlier_phones = set(
            db.scalars(
                select(Order.phone)
                .where(Order.pickup_date < date_from, Order.phone.in_(period_phones))
                .distinct()
            ).all()
        )

    top_products = sorted(
        (
            {
                "title": item["title"],
                "quantity": round(item["quantity"], 3),
                "revenue": round(item["revenue"], 2),
            }
            for item in top.values()
        ),
        key=lambda item: item["revenue"],
        reverse=True,
    )[:12]

    return {
        "range": {"from": date_from.isoformat(), "to": date_to.isoformat(), "days": len(daily)},
        "kpis": {
            "orders": len(orders),
            "completed": completed,
            "revenue": round(revenue, 2),
            "avg_check": round(revenue / completed, 2) if completed else 0.0,
            "new_customers": len(period_phones - earlier_phones),
            "items_sold": round(items_sold, 3),
            "discount": round(discount, 2),
            "delivery_fee": round(delivery_fee, 2),
            "cancelled": statuses.get(ORDER_CANCELLED, 0) + statuses.get(ORDER_REJECTED, 0),
        },
        "daily": list(daily.values()),
        "statuses": [
            {"code": code, "label": label, "count": statuses.get(code, 0)}
            for code, label in STATUS_LABELS.items()
        ],
        "fulfillment": fulfillment,
        "top_products": top_products,
        "categories": [
            {"title": title, "revenue": round(value, 2)}
            for title, value in sorted(categories.items(), key=lambda pair: pair[1], reverse=True)
        ],
    }


@router.get("/reports", summary="Отчёт по продажам за период")
def reports(
    days: int = Query(default=30, ge=1, le=365),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    date_from, date_to = _report_range(days)
    return build_report(db, date_from, date_to)


@router.get("/reports/export.csv", summary="Экспорт отчёта в CSV")
def export_report(
    kind: str = Query(default="daily", pattern="^(daily|products|statuses|orders|categories)$"),
    days: int = Query(default=30, ge=1, le=365),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    date_from, date_to = _report_range(days)
    report = build_report(db, date_from, date_to)
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer, delimiter=";")

    if kind == "daily":
        writer.writerow(["Дата", "Заказов", "Выдано", "Выручка BYN"])
        for row in report["daily"]:
            writer.writerow([
                date.fromisoformat(row["date"]).strftime("%d.%m.%Y"),
                row["orders"],
                row["completed"],
                f"{row['revenue']:.2f}".replace(".", ","),
            ])
    elif kind == "products":
        writer.writerow(["Товар", "Количество", "Выручка BYN"])
        for row in report["top_products"]:
            writer.writerow([row["title"], f"{row['quantity']:g}".replace(".", ","), f"{row['revenue']:.2f}".replace(".", ",")])
    elif kind == "statuses":
        writer.writerow(["Статус", "Заказов"])
        for row in report["statuses"]:
            writer.writerow([row["label"], row["count"]])
    elif kind == "categories":
        writer.writerow(["Категория", "Выручка BYN"])
        for row in report["categories"]:
            writer.writerow([row["title"], f"{row['revenue']:.2f}".replace(".", ",")])
    else:
        writer.writerow([
            "Номер", "Создан", "Клиент", "Телефон", "Дата выдачи", "Время", "Статус",
            "Получение", "Зона", "Адрес", "Сумма BYN", "Скидка BYN", "Доставка BYN", "Промокод",
        ])
        orders = db.scalars(
            select(Order)
            .where(Order.pickup_date >= date_from, Order.pickup_date <= date_to)
            .order_by(Order.created_at.desc())
        ).unique().all()
        for order in orders:
            writer.writerow([
                order.number,
                order.created_at.strftime("%d.%m.%Y %H:%M"),
                order.customer_name,
                format_phone(order.phone),
                order.pickup_date.strftime("%d.%m.%Y"),
                order.pickup_time,
                STATUS_LABELS.get(order.status, order.status),
                "Доставка" if order.fulfillment == "delivery" else "Самовывоз",
                order.delivery_zone_name or "",
                order.delivery_address or "",
                f"{float(order.total_amount):.2f}".replace(".", ","),
                f"{float(order.discount_amount):.2f}".replace(".", ","),
                f"{float(order.delivery_fee):.2f}".replace(".", ","),
                order.promo_code or "",
            ])

    filename = f"report-{kind}-{date_from.isoformat()}-{date_to.isoformat()}.csv"
    return Response(
        content=buffer.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/orders/export.csv", summary="Экспорт броней в CSV")
def export_orders(
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(Order).order_by(Order.created_at.desc())
    if status and status != "all":
        stmt = stmt.where(Order.status == status)
    if date_from:
        stmt = stmt.where(Order.pickup_date >= date_from)
    if date_to:
        stmt = stmt.where(Order.pickup_date <= date_to)
    rows = db.scalars(stmt).unique().all()

    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Номер", "Создан", "Клиент", "Телефон", "Дата выдачи", "Время", "Статус", "Сумма BYN", "Позиции"])
    labels = {
        "new": "Новая", "confirmed": "Подтверждена", "ready": "Готова",
        "completed": "Выдана", "cancelled": "Отменена", "rejected": "Отклонена",
    }
    for order in rows:
        writer.writerow([
            order.number,
            order.created_at.strftime("%d.%m.%Y %H:%M"),
            order.customer_name,
            format_phone(order.phone),
            order.pickup_date.strftime("%d.%m.%Y"),
            order.pickup_time,
            labels.get(order.status, order.status),
            f"{float(order.total_amount):.2f}".replace(".", ","),
            "; ".join(f"{i.title} — {float(i.quantity):g} {i.unit}" for i in order.items),
        ])
    content = buffer.getvalue().encode("utf-8")
    filename = f"orders-{local_today().isoformat()}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/orders/{order_id}", response_model=OrderOut, summary="Детали брони")
def admin_order(order_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    order = tenant_get(db, Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Бронь не найдена")
    return order_payload(order)


@router.patch("/orders/{order_id}", response_model=OrderOut, summary="Изменить бронь и статус")
def admin_update_order(
    order_id: int,
    payload: OrderStatusIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    order = tenant_get(db, Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Бронь не найдена")
    if payload.admin_comment is not None:
        order.admin_comment = payload.admin_comment.strip()
    if payload.pickup_date:
        order.pickup_date = payload.pickup_date
    if payload.pickup_time:
        order.pickup_time = payload.pickup_time
    actor = f"{user.full_name or user.phone} (администратор)"
    order = transition_order(db, order, payload.status, actor=actor, comment=payload.admin_comment or "")
    audit(db, "order.update", actor=user.phone, user_id=user.id, entity="order", entity_id=order.id,
          details={"status": payload.status})
    db.commit()
    return order_payload(order)


# ─────────────────────────── Пользователи ───────────────────────────

@router.get("/users", summary="Зарегистрированные пользователи")
def admin_users(
    q: str | None = None,
    role: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(User)
    count_stmt = select(func.count(User.id))
    if q:
        pattern = f"%{q.strip()}%"
        clause = or_(User.phone.ilike(pattern), User.full_name.ilike(pattern), User.email.ilike(pattern))
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)
    if role and role != "all":
        stmt = stmt.where(User.role == role)
        count_stmt = count_stmt.where(User.role == role)
    rows = db.scalars(stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)).all()

    order_stats = {
        row[0]: (int(row[1]), row[2])
        for row in db.execute(
            select(Order.user_id, func.count(Order.id), func.max(Order.created_at))
            .where(Order.user_id.is_not(None))
            .group_by(Order.user_id)
        ).all()
    }
    items = []
    for user in rows:
        count, last = order_stats.get(user.id, (0, None))
        data = UserAdminOut.model_validate(user).model_dump()
        data["orders_count"] = count
        data["last_order_at"] = last
        data["phone_formatted"] = format_phone(user.phone)
        items.append(data)
    return {"items": items, "total": int(db.scalar(count_stmt) or 0)}


@router.post("/users", summary="Создать сотрудника")
def create_staff(
    payload: AdminUserCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.scalar(select(User).where(User.phone == payload.phone)):
        raise HTTPException(status_code=400, detail="Пользователь с таким номером уже существует")
    try:
        validate_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    user = User(
        phone=payload.phone,
        full_name=payload.full_name.strip(),
        role=payload.role,
        password_hash=hash_password(payload.password),
        is_phone_verified=True,
        consent_personal_data=True,
    )
    db.add(user)
    db.flush()
    audit(db, "user.create_staff", actor=admin.phone, user_id=admin.id, entity="user", entity_id=user.id,
          details={"role": payload.role})
    db.commit()
    return {"ok": True, "id": user.id, "message": "Сотрудник создан. Пароль нужно передать лично."}


@router.patch("/users/{user_id}", summary="Изменить пользователя или роль")
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = tenant_get(db, User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if user.id == admin.id:
        if payload.role and payload.role != ROLE_ADMIN:
            raise HTTPException(status_code=400, detail="Нельзя снять права администратора с самого себя")
        if payload.is_active is False:
            raise HTTPException(status_code=400, detail="Нельзя заблокировать свою учётную запись")

    if payload.role and user.role == ROLE_ADMIN and payload.role != ROLE_ADMIN:
        admins = db.scalar(select(func.count(User.id)).where(User.role == ROLE_ADMIN, User.is_active.is_(True))) or 0
        if admins <= 1:
            raise HTTPException(status_code=400, detail="В системе должен остаться хотя бы один администратор")

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.email is not None:
        user.email = str(payload.email)
    if payload.role is not None:
        user.role = payload.role
        user.is_phone_verified = True
    if payload.is_active is not None:
        user.is_active = payload.is_active

    audit(db, "user.update", actor=admin.phone, user_id=admin.id, entity="user", entity_id=user.id,
          details=payload.model_dump(exclude_none=True))
    db.commit()
    return {"ok": True, "message": "Данные пользователя обновлены"}


@router.post("/users/{user_id}/role", summary="Назначить роль")
def set_role(user_id: int, payload: RoleIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return update_user(user_id, AdminUserUpdate(role=payload.role), admin=admin, db=db)


@router.post("/users/{user_id}/block", summary="Заблокировать или разблокировать")
def block_user(user_id: int, payload: ActiveIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return update_user(user_id, AdminUserUpdate(is_active=payload.is_active), admin=admin, db=db)


# ─────────────────────────── QR-коды ───────────────────────────

@router.get("/qr/items", summary="Список QR-кодов сайта и товаров")
def qr_items(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    items = [
        {
            "kind": "site",
            "target": "site",
            "title": "Главная страница сайта",
            "url": site_url(),
            "qr_url": "/api/qr/site.png?size=640",
            "download_url": "/api/qr/site.png?size=1000&download=1",
        }
    ]
    products = db.scalars(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.sort_order, Product.title)
    ).all()
    for product in products:
        items.append(
            {
                "kind": "product",
                "target": product.slug,
                "title": product.title,
                "url": product_url(product.slug),
                "qr_url": f"/api/qr/product/{product.slug}.png?size=640",
                "download_url": f"/api/qr/product/{product.slug}.png?size=1000&download=1",
            }
        )
    return {"items": items, "total": len(items)}


# ─────────────────────────── Журнал и загрузки ───────────────────────────

@router.post("/uploads", response_model=UploadOut, summary="Загрузить изображение")
def upload(file: UploadFile = File(...), _: User = Depends(require_admin)):
    return save_image(file)


@router.get("/audit", summary="Журнал действий")
def audit_log(limit: int = Query(default=100, ge=1, le=500), _: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return {
        "items": [
            {
                "id": row.id,
                "actor": row.actor,
                "action": row.action,
                "entity": row.entity,
                "entity_id": row.entity_id,
                "details": row.details,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }
