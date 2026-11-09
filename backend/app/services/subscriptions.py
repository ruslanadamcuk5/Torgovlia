"""Регулярные заказы: подписка, состав, ближайшая дата и создание заказа."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    SUB_ACTIVE,
    SUB_CANCELLED,
    SUB_INTERVALS,
    SUB_PAUSED,
    DeliveryZone,
    Order,
    Product,
    RegularOrder,
    RegularOrderItem,
    User,
)
from app.platform.sync import is_enabled
from app.schemas import OrderCreateIn, OrderItemIn, SubscriptionItemIn
from app.services.orders import create_order, get_slots
from app.services.settings import get_settings_model
from app.tenancy import current_tenant
from app.utils import local_today, money, qty


STATUS_LABELS = {
    SUB_ACTIVE: "Активна",
    SUB_PAUSED: "На паузе",
    SUB_CANCELLED: "Отменена",
}
INTERVAL_LABELS = {7: "Раз в неделю", 14: "Раз в две недели", 30: "Раз в месяц"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def require_enabled(db: Session) -> int:
    context = current_tenant()
    if not context:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    if not is_enabled(db, context.id, "subscriptions"):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "service_disabled",
                "message": "Сервис «Регулярные заказы» не подключён. Включите его в разделе «Сервисы».",
            },
        )
    return context.id


def get_subscription(db: Session, sub_id: int) -> Subscription:
    sub = db.scalar(select(RegularOrder).where(RegularOrder.id == sub_id))
    if not sub:
        raise HTTPException(status_code=404, detail="Регулярный заказ не найден")
    return sub


def _current_price(product: Product) -> Decimal:
    discount = max(0, min(95, int(product.discount_percent or 0)))
    return money(Decimal(product.price) * (100 - discount) / 100)


def _delivery_zone(db: Session, zone_id: int | None) -> DeliveryZone | None:
    """Зона доставки: выбранная владельцем или первая активная по умолчанию."""
    if zone_id:
        zone = db.get(DeliveryZone, zone_id)
        if not zone or not zone.is_active:
            raise HTTPException(status_code=422, detail="Эта зона доставки недоступна")
        return zone
    return db.scalar(
        select(DeliveryZone)
        .where(DeliveryZone.is_active.is_(True))
        .order_by(DeliveryZone.fee, DeliveryZone.id)
        .limit(1)
    )


def item_payload(item: RegularOrderItem, product: Product | None) -> dict:
    quantity = Decimal(item.quantity or 0)
    available = bool(product and product.is_active and product.is_available)
    if product and product.stock is not None:
        available = available and Decimal(product.stock) >= quantity
    price = _current_price(product) if product else Decimal("0.00")
    return {
        "id": item.id,
        "product_id": item.product_id,
        "title": (product.title if product else item.title) or "Товар удалён",
        "image_url": product.image_url if product else "",
        "unit": product.unit if product else item.unit,
        "quantity": float(quantity),
        "price": float(price),
        "line_total": float(money(price * quantity)),
        "available": available,
        "stock": float(product.stock) if product and product.stock is not None else None,
    }


def items_for(db: Session, sub_ids: list[int]) -> dict[int, list[RegularOrderItem]]:
    if not sub_ids:
        return {}
    rows = db.scalars(
        select(RegularOrderItem).where(RegularOrderItem.subscription_id.in_(sub_ids))
    ).all()
    result: dict[int, list[RegularOrderItem]] = {sub_id: [] for sub_id in sub_ids}
    for row in rows:
        result.setdefault(row.subscription_id, []).append(row)
    return result


def _products(db: Session, items: list[RegularOrderItem]) -> dict[int, Product]:
    ids = {item.product_id for item in items if item.product_id}
    if not ids:
        return {}
    rows = db.scalars(select(Product).where(Product.id.in_(ids))).all()
    return {product.id: product for product in rows}


def payload(
    db: Session,
    sub: RegularOrder,
    items: list[RegularOrderItem],
    last_order: Order | None = None,
) -> dict:
    products = _products(db, items)
    zone = db.get(DeliveryZone, sub.delivery_zone_id) if sub.delivery_zone_id else None
    today = local_today()
    next_date = sub.next_order_date
    return {
        "id": sub.id,
        "user_id": sub.user_id,
        "customer_name": sub.customer_name,
        "phone": sub.phone,
        "interval_days": sub.interval_days,
        "interval_label": INTERVAL_LABELS.get(sub.interval_days, f"Каждые {sub.interval_days} дн."),
        "status": sub.status,
        "status_label": STATUS_LABELS.get(sub.status, sub.status),
        "next_order_date": next_date.isoformat() if next_date else None,
        "due_today": bool(sub.status == SUB_ACTIVE and next_date and next_date <= today),
        "overdue_days": max(0, (today - next_date).days)
        if sub.status == SUB_ACTIVE and next_date
        else 0,
        "last_order_at": sub.last_order_at.isoformat() if sub.last_order_at else None,
        "last_order": (
            {
                "id": last_order.id,
                "number": last_order.number,
                "status": last_order.status,
                "total": float(last_order.total_amount or 0),
                "pickup_date": last_order.pickup_date.isoformat(),
            }
            if last_order
            else None
        ),
        "last_error": sub.last_error or "",
        "fulfillment": sub.fulfillment or "pickup",
        "delivery_zone_id": sub.delivery_zone_id,
        "delivery_zone_name": zone.name if zone else "",
        "delivery_fee": float(zone.fee or 0) if zone else 0,
        "delivery_address": sub.delivery_address or "",
        "comment": sub.comment or "",
        "items": [item_payload(item, products.get(item.product_id)) for item in items],
        "items_count": len(items),
        "total": float(
            sum(
                item_payload(item, products.get(item.product_id))["line_total"]
                for item in items
            )
        ),
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
    }


def list_subscriptions(
    db: Session,
    status: str | None = None,
    q: str | None = None,
    user_id: int | None = None,
    limit: int = 300,
) -> list[dict]:
    stmt = select(RegularOrder)
    if status and status != "all":
        stmt = stmt.where(RegularOrder.status == status)
    if user_id is not None:
        stmt = stmt.where(RegularOrder.user_id == user_id)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                RegularOrder.customer_name.ilike(pattern),
                RegularOrder.phone.ilike(pattern),
            )
        )
    stmt = stmt.order_by(
        RegularOrder.status != SUB_ACTIVE,
        RegularOrder.next_order_date,
        RegularOrder.id.desc(),
    ).limit(limit)
    subs = list(db.scalars(stmt).all())
    grouped = items_for(db, [sub.id for sub in subs])
    order_ids = {sub.last_order_id for sub in subs if sub.last_order_id}
    orders = (
        {order.id: order for order in db.scalars(select(Order).where(Order.id.in_(order_ids))).all()}
        if order_ids
        else {}
    )
    return [
        payload(db, sub, grouped.get(sub.id, []), orders.get(sub.last_order_id))
        for sub in subs
    ]


def summary(db: Session) -> dict:
    subs = list(db.scalars(select(RegularOrder)).all())
    today = local_today()
    soon = today + timedelta(days=7)
    active = [sub for sub in subs if sub.status == SUB_ACTIVE]
    return {
        "total": len(subs),
        "active": len(active),
        "paused": sum(1 for sub in subs if sub.status == SUB_PAUSED),
        "cancelled": sum(1 for sub in subs if sub.status == SUB_CANCELLED),
        "due": sum(1 for sub in active if sub.next_order_date <= today),
        "soon": sum(1 for sub in active if sub.next_order_date <= soon),
        "with_errors": sum(1 for sub in active if sub.last_error),
    }


def validate_items(db: Session, items: list[RegularOrderItemIn]) -> list[tuple[Product, Decimal]]:
    if not items:
        raise HTTPException(status_code=422, detail="Добавьте хотя бы один товар")
    merged: dict[int, Decimal] = {}
    for item in items:
        merged[item.product_id] = merged.get(item.product_id, Decimal("0")) + Decimal(
            str(item.quantity)
        )
    products = {
        product.id: product
        for product in db.scalars(select(Product).where(Product.id.in_(merged))).all()
    }
    result: list[tuple[Product, Decimal]] = []
    for product_id, quantity in merged.items():
        product = products.get(product_id)
        if not product or not product.is_active:
            raise HTTPException(
                status_code=422,
                detail="Один из товаров больше не продаётся. Обновите состав подписки.",
            )
        if quantity <= 0:
            raise HTTPException(status_code=422, detail="Количество должно быть больше нуля")
        if product.unit == "piece":
            quantity = qty(quantity.quantize(Decimal("1")))
        result.append((product, quantity))
    return result


def _replace_items(
    db: Session, sub: RegularOrder, items: list[tuple[Product, Decimal]]
) -> None:
    db.execute(
        delete(RegularOrderItem).where(
            RegularOrderItem.tenant_id == sub.tenant_id,
            RegularOrderItem.subscription_id == sub.id,
        )
    )
    for product, quantity in items:
        db.add(
            RegularOrderItem(
                tenant_id=sub.tenant_id,
                subscription_id=sub.id,
                product_id=product.id,
                title=product.title,
                unit=product.unit,
                quantity=quantity,
            )
        )


def create(
    db: Session,
    tenant_id: int,
    *,
    customer_name: str,
    phone: str,
    interval_days: int,
    next_order_date: date,
    items: list[RegularOrderItemIn],
    fulfillment: str = "pickup",
    delivery_zone_id: int | None = None,
    delivery_address: str = "",
    comment: str = "",
    user_id: int | None = None,
) -> RegularOrder:
    if interval_days not in SUB_INTERVALS:
        raise HTTPException(status_code=422, detail="Интервал: 7, 14 или 30 дней")
    if next_order_date < local_today():
        raise HTTPException(status_code=422, detail="Дата первого заказа уже прошла")
    zone = None
    if fulfillment == "delivery":
        zone = _delivery_zone(db, delivery_zone_id)
        if not zone:
            raise HTTPException(status_code=422, detail="Нет активных зон доставки")
        if len(delivery_address.strip()) < 5:
            raise HTTPException(status_code=422, detail="Укажите адрес доставки: улица, дом, квартира")
    prepared = validate_items(db, items)
    sub = RegularOrder(
        tenant_id=tenant_id,
        user_id=user_id,
        customer_name=customer_name.strip()[:120],
        phone=phone,
        interval_days=interval_days,
        status=SUB_ACTIVE,
        next_order_date=next_order_date,
        fulfillment=fulfillment,
        delivery_zone_id=zone.id if zone else None,
        delivery_address=delivery_address.strip(),
        comment=comment.strip(),
    )
    db.add(sub)
    db.flush()
    _replace_items(db, sub, prepared)
    return sub


def update(
    db: Session,
    sub: RegularOrder,
    *,
    status: str | None = None,
    interval_days: int | None = None,
    next_order_date: date | None = None,
    items: list[RegularOrderItemIn] | None = None,
    fulfillment: str | None = None,
    delivery_zone_id: int | None = None,
    delivery_address: str | None = None,
    comment: str | None = None,
) -> RegularOrder:
    if interval_days is not None:
        if interval_days not in SUB_INTERVALS:
            raise HTTPException(status_code=422, detail="Интервал: 7, 14 или 30 дней")
        sub.interval_days = interval_days
    if next_order_date is not None:
        if next_order_date < local_today():
            raise HTTPException(status_code=422, detail="Дата следующего заказа уже прошла")
        sub.next_order_date = next_order_date
    if items is not None:
        _replace_items(db, sub, validate_items(db, items))
    if fulfillment is not None:
        sub.fulfillment = fulfillment
    if delivery_zone_id is not None:
        zone = _delivery_zone(db, delivery_zone_id)
        sub.delivery_zone_id = zone.id if zone else None
    if delivery_address is not None:
        sub.delivery_address = delivery_address.strip()
    if sub.fulfillment == "delivery":
        zone = _delivery_zone(db, sub.delivery_zone_id)
        if not zone:
            raise HTTPException(status_code=422, detail="Нет активных зон доставки")
        sub.delivery_zone_id = zone.id
        if len(sub.delivery_address) < 5:
            raise HTTPException(status_code=422, detail="Укажите адрес доставки: улица, дом, квартира")
    if comment is not None:
        sub.comment = comment.strip()
    if status and status != sub.status:
        if status not in STATUS_LABELS:
            raise HTTPException(status_code=422, detail="Неизвестный статус подписки")
        sub.status = status
        if status == SUB_ACTIVE and sub.next_order_date < local_today():
            sub.next_order_date = local_today()
        sub.last_error = ""
    sub.updated_at = _now()
    return sub


def _first_slot(db: Session, start: date) -> tuple[date, str]:
    conf = get_settings_model(db)
    day = max(start, local_today())
    for _ in range(max(1, conf.booking_days_ahead) + 1):
        data = get_slots(db, day)
        if data.get("is_open"):
            slot = next((row for row in data["slots"] if row["available"]), None)
            if slot:
                return day, slot["time"]
        day += timedelta(days=1)
    raise HTTPException(
        status_code=409,
        detail="Нет свободных окон для регулярного заказа. Проверьте график работы и вместимость слотов.",
    )


def _advance(sub: RegularOrder, scheduled: date) -> None:
    today = local_today()
    next_date = scheduled + timedelta(days=sub.interval_days)
    while next_date <= today:
        next_date += timedelta(days=sub.interval_days)
    sub.next_order_date = next_date


def create_order_for(
    db: Session, sub: RegularOrder, scheduled: date | None = None
) -> Order:
    if sub.status != SUB_ACTIVE:
        raise HTTPException(status_code=409, detail="Подписка на паузе или отменена")
    grouped = items_for(db, [sub.id]).get(sub.id, [])
    if not grouped:
        raise HTTPException(status_code=422, detail="В подписке нет товаров")
    scheduled = scheduled or sub.next_order_date
    pickup_date, pickup_time = _first_slot(db, scheduled)
    user = db.get(User, sub.user_id) if sub.user_id else None
    order_items = [
        OrderItemIn(product_id=item.product_id, quantity=float(item.quantity or 0))
        for item in grouped
        if item.product_id
    ]
    if not order_items:
        raise HTTPException(status_code=422, detail="Товары подписки удалены из каталога")
    zone_id = sub.delivery_zone_id
    if (sub.fulfillment or "pickup") == "delivery" and not zone_id:
        zone = _delivery_zone(db, None)
        if not zone:
            raise HTTPException(status_code=422, detail="Нет активных зон доставки")
        zone_id = zone.id
    payload_in = OrderCreateIn(
        items=order_items,
        pickup_date=pickup_date,
        pickup_time=pickup_time,
        customer_name=sub.customer_name,
        comment=(f"Регулярный заказ №{sub.id}" + (f". {sub.comment}" if sub.comment else ""))[:600],
        fulfillment=sub.fulfillment or "pickup",
        delivery_zone_id=zone_id,
        delivery_address=sub.delivery_address or "",
        consent_personal_data=True,
    )
    order = create_order(db, payload_in, phone=sub.phone, user=user)
    sub.last_order_id = order.id
    sub.last_order_at = _now()
    sub.last_error = ""
    _advance(sub, scheduled)
    return order


def run_now(db: Session, sub: RegularOrder) -> Order:
    return create_order_for(db, sub, scheduled=local_today())


def materialize_due(db: Session) -> list[Order]:
    """Создаёт заказы по подпискам, у которых наступила дата. Ленивый запуск."""
    today = local_today()
    ids = list(
        db.scalars(
            select(RegularOrder.id)
            .where(
                RegularOrder.status == SUB_ACTIVE,
                RegularOrder.next_order_date <= today,
            )
            .order_by(RegularOrder.next_order_date)
        ).all()
    )
    created: list[Order] = []
    for sub_id in ids:
        try:
            sub = get_subscription(db, sub_id)
            order = create_order_for(db, sub)
            db.commit()
            created.append(order)
        except HTTPException as exc:
            db.rollback()
            sub = get_subscription(db, sub_id)
            sub.last_error = str(exc.detail)[:500]
            sub.updated_at = _now()
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
            sub = get_subscription(db, sub_id)
            sub.last_error = "Не удалось создать заказ. Проверьте товары и остатки."
            sub.updated_at = _now()
            db.commit()
    return created


def count_active(db: Session, user_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(RegularOrder.id)).where(
                RegularOrder.user_id == user_id,
                RegularOrder.status == SUB_ACTIVE,
            )
        )
        or 0
    )
