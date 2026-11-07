"""Логика бронирования: слоты, проверки, создание и смена статусов заказа."""

import secrets
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.tenancy import current_tenant, tenant_get
from app.models import (
    ORDER_CANCELLED,
    ORDER_COMPLETED,
    ORDER_CONFIRMED,
    ORDER_NEW,
    ORDER_READY,
    ORDER_REJECTED,
    Order,
    OrderItem,
    Product,
    User,
)
from app.schemas import OrderCreateIn
from app.services.audit import audit
from app.services.promotions import find_promo, redeem, resolve
from app.services.settings import get_settings_model
from app.utils import local_now, local_today, money, qty


ACTIVE_STATUSES = (ORDER_NEW, ORDER_CONFIRMED, ORDER_READY)

TRANSITIONS = {
    ORDER_NEW: {ORDER_CONFIRMED, ORDER_CANCELLED, ORDER_REJECTED},
    ORDER_CONFIRMED: {ORDER_READY, ORDER_CANCELLED, ORDER_REJECTED},
    ORDER_READY: {ORDER_COMPLETED, ORDER_CANCELLED, ORDER_REJECTED},
    ORDER_COMPLETED: set(),
    ORDER_CANCELLED: set(),
    ORDER_REJECTED: set(),
}


def _parse_time(value: str) -> time:
    try:
        hours, minutes = value.split(":")
        return time(int(hours), int(minutes))
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Некорректное время") from exc


def _slot_datetimes(open_s: str, close_s: str, step: int) -> list[str]:
    start = datetime.combine(date.today(), _parse_time(open_s))
    end = datetime.combine(date.today(), _parse_time(close_s))
    result: list[str] = []
    current = start
    while current < end:
        result.append(current.strftime("%H:%M"))
        current += timedelta(minutes=max(10, step))
    return result


def _booked_counts(db: Session, target_date: date) -> dict[str, int]:
    rows = db.execute(
        select(Order.pickup_time, func.count(Order.id))
        .where(Order.pickup_date == target_date, Order.status.in_(ACTIVE_STATUSES))
        .group_by(Order.pickup_time)
    ).all()
    return {row[0]: int(row[1]) for row in rows}


def get_slots(db: Session, target_date: date) -> dict:
    conf = get_settings_model(db)
    today = local_today()
    max_date = today + timedelta(days=max(1, conf.booking_days_ahead))

    if target_date < today:
        return {"date": target_date, "is_open": False, "slots": [], "message": "Дата уже прошла"}
    if target_date > max_date:
        return {
            "date": target_date,
            "is_open": False,
            "slots": [],
            "message": f"Бронирование доступно на {conf.booking_days_ahead} дней вперёд",
        }

    weekday = target_date.weekday()
    hours = next((h for h in conf.working_hours if h.weekday == weekday), None)
    if not hours or hours.closed:
        return {"date": target_date, "is_open": False, "slots": [], "message": "В этот день павильон не работает"}

    now = local_now().replace(tzinfo=None)
    min_time = now + timedelta(minutes=max(0, conf.lead_time_minutes))
    booked = _booked_counts(db, target_date)
    slots = []
    for slot in _slot_datetimes(hours.open, hours.close, conf.slot_step_minutes):
        slot_dt = datetime.combine(target_date, _parse_time(slot))
        capacity_left = max(0, conf.slot_capacity - booked.get(slot, 0))
        too_early = slot_dt < min_time
        slots.append(
            {
                "time": slot,
                "available": (not too_early) and capacity_left > 0,
                "capacity_left": capacity_left,
            }
        )

    available_count = sum(1 for s in slots if s["available"])
    message = ""
    if not available_count:
        message = "На сегодня свободных окон нет — выберите другую дату или позвоните нам"
    return {"date": target_date, "is_open": True, "slots": slots, "message": message}


def validate_pickup(db: Session, target_date: date, pickup_time: str) -> None:
    data = get_slots(db, target_date)
    if not data["is_open"]:
        raise HTTPException(status_code=400, detail=data["message"] or "Павильон не работает в этот день")
    slot = next((s for s in data["slots"] if s["time"] == pickup_time), None)
    if not slot:
        raise HTTPException(status_code=400, detail="Выберите время из доступных интервалов")
    if not slot["available"]:
        raise HTTPException(
            status_code=400,
            detail="Это время уже занято. Выберите другой интервал — мы ограничиваем количество броней на слот.",
        )


def _generate_number(db: Session) -> str:
    prefix = local_now().strftime("%y%m%d")
    for _ in range(20):
        candidate = f"RL-{prefix}-{secrets.randbelow(9000) + 1000}"
        exists = db.scalar(select(Order.id).where(Order.number == candidate))
        if not exists:
            return candidate
    return f"RL-{prefix}-{secrets.token_hex(3).upper()}"


def create_order(
    db: Session,
    payload: OrderCreateIn,
    phone: str,
    user: User | None = None,
) -> Order:
    conf = get_settings_model(db)
    validate_pickup(db, payload.pickup_date, payload.pickup_time)

    requested: dict[int, Decimal] = {}
    for item in payload.items:
        requested[item.product_id] = requested.get(item.product_id, Decimal("0")) + qty(item.quantity)

    if len(requested) > conf.max_items:
        raise HTTPException(status_code=400, detail=f"В одном заказе может быть не более {conf.max_items} позиций")

    items: list[OrderItem] = []
    total = Decimal("0.00")
    total_units = 0

    for product_id, quantity in requested.items():
        # Блокируем строку товара на время транзакции, чтобы два покупателя
        # не смогли одновременно списать один и тот же остаток.
        product = db.scalar(select(Product).where(Product.id == product_id).with_for_update())
        if not product or not product.is_active:
            raise HTTPException(status_code=400, detail="Один из товаров больше не продаётся. Обновите корзину.")
        if not product.is_available or (product.stock is not None and product.stock <= 0):
            raise HTTPException(
                status_code=400,
                detail=f"«{product.title}» сегодня нет в наличии. Уберите товар из заказа или выберите аналог.",
            )
        unit_label = "кг" if product.unit == "kg" else "шт."
        if product.stock is not None and quantity > product.stock:
            raise HTTPException(
                status_code=400,
                detail=f"«{product.title}»: доступно {float(product.stock):g} {unit_label}. Уменьшите количество.",
            )
        if product.unit == "kg" and quantity > 50:
            raise HTTPException(status_code=400, detail=f"«{product.title}»: слишком большой вес для одной брони")
        if product.unit == "piece":
            quantity = qty(quantity.quantize(Decimal("1")))

        discount = max(0, min(95, int(product.discount_percent or 0)))
        unit_price = money(Decimal(product.price) * (100 - discount) / 100)
        line_total = money(unit_price * quantity)
        total += line_total
        total_units += 1

        items.append(
            OrderItem(
                product_id=product.id,
                title=product.title,
                image_url=product.image_url,
                unit=product.unit,
                price=unit_price,
                quantity=quantity,
                line_total=line_total,
            )
        )
        if product.stock is not None:
            product.stock = Decimal(product.stock) - quantity

    if total < Decimal(str(conf.min_order_amount)):
        raise HTTPException(
            status_code=400,
            detail=f"Минимальная сумма брони — {conf.min_order_amount:.2f} BYN".replace(".", ","),
        )

    subtotal = total
    discount = Decimal("0.00")
    promo = None
    if payload.promo_code:
        tenant = current_tenant()
        if tenant:
            from app.platform.sync import is_enabled

            if not is_enabled(db, tenant.id, "promo_codes"):
                raise HTTPException(status_code=400, detail="Промокоды не подключены в вашем тарифе")
        promo, discount, total = resolve(db, payload.promo_code, total)

    delivery_fee = Decimal("0.00")
    delivery_zone = None
    delivery_address = ""
    if payload.fulfillment == "delivery":
        from app.services.delivery import feature_enabled as delivery_enabled
        from app.services.delivery import resolve as resolve_delivery

        if not delivery_enabled(db):
            raise HTTPException(status_code=400, detail="Доставка не подключена в вашем тарифе")
        delivery_address = (payload.delivery_address or "").strip()
        if len(delivery_address) < 5:
            raise HTTPException(status_code=400, detail="Укажите адрес доставки: улица, дом, квартира")
        delivery_zone, delivery_fee = resolve_delivery(db, payload.delivery_zone_id, subtotal)
        total = money(total + delivery_fee)

    order = Order(
        number=_generate_number(db),
        user_id=user.id if user else None,
        customer_name=payload.customer_name.strip(),
        phone=phone,
        pickup_date=payload.pickup_date,
        pickup_time=payload.pickup_time,
        status=ORDER_NEW,
        comment=payload.comment,
        total_amount=money(total),
        discount_amount=money(discount),
        promo_code=promo.code if promo else "",
        fulfillment=payload.fulfillment,
        delivery_zone_id=delivery_zone.id if delivery_zone else None,
        delivery_zone_name=delivery_zone.name if delivery_zone else "",
        delivery_address=delivery_address,
        delivery_fee=money(delivery_fee),
        items_count=total_units,
        source=payload.source,
        status_history=[
            {
                "status": ORDER_NEW,
                "at": datetime.now(timezone.utc).isoformat(),
                "by": "client",
                "comment": "Заказ оформлен",
            }
        ],
        items=items,
    )
    db.add(order)
    db.flush()
    if promo:
        redeem(promo)
    # Фиксируем факт согласия на обработку персональных данных для доказуемости
    # (ст. 5 Закона Республики Беларусь от 07.05.2021 № 99-З).
    audit(
        db,
        action="order_consent",
        actor="client",
        user_id=user.id if user else None,
        entity="order",
        entity_id=order.number,
        details={
            "phone": phone,
            "source": payload.source,
            "policy": "privacy_policy",
            "consent": True,
        },
    )
    db.commit()
    db.refresh(order)
    return order


def transition_order(db: Session, order: Order, new_status: str, actor: str, comment: str = "") -> Order:
    if new_status == order.status:
        return order
    allowed = TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя перевести заказ из статуса «{order.status}» в «{new_status}»",
        )

    if new_status in (ORDER_CANCELLED, ORDER_REJECTED):
        for item in order.items:
            if item.product_id:
                product = tenant_get(db, Product, item.product_id)
                if product and product.stock is not None:
                    product.stock = Decimal(product.stock) + Decimal(item.quantity)
        # Отменённая бронь не должна «съедать» лимит промокода.
        if order.promo_code:
            promo = find_promo(db, order.promo_code)
            if promo and promo.used_count > 0:
                promo.used_count -= 1

    order.status = new_status
    history = list(order.status_history or [])
    history.append(
        {
            "status": new_status,
            "at": datetime.now(timezone.utc).isoformat(),
            "by": actor,
            "comment": comment,
        }
    )
    order.status_history = history
    db.commit()
    db.refresh(order)
    return order


def cancel_by_customer(db: Session, order: Order) -> Order:
    if order.status not in (ORDER_NEW, ORDER_CONFIRMED):
        raise HTTPException(
            status_code=400,
            detail="Заказ уже собирается или передан. Для отмены свяжитесь с павильоном.",
        )
    return transition_order(db, order, ORDER_CANCELLED, actor="client", comment="Отменён покупателем")
