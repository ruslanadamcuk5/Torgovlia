"""Корзины покупателей и напоминания о брошенной корзине."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Cart, Product, User
from app.security import format_phone, normalize_phone
from app.services.notifications import channels_status, send_email
from app.services.settings import get_settings_model
from app.services.sms import SmsError, send_sms
from app.tenancy import tenant_get
from app.utils import money, qty


log = logging.getLogger("torgovlia.carts")

ABANDON_MINUTES = 60
REMIND_COOLDOWN_HOURS = 24
MAX_SYNC_ITEMS = 60
MAX_REMINDERS_PER_RUN = 50


def _now() -> datetime:
    return datetime.now(timezone.utc)


def final_price(product: Product) -> Decimal:
    price = money(product.price or 0)
    discount = max(0, min(95, int(product.discount_percent or 0)))
    return money(price * (100 - discount) / 100)


def _cart_items(db: Session, payload) -> tuple[list[dict], Decimal]:
    items: list[dict] = []
    total = Decimal("0.00")
    for row in payload.items[:MAX_SYNC_ITEMS]:
        product = tenant_get(db, Product, row.product_id)
        if not product or not product.is_active:
            continue
        quantity = qty(row.quantity)
        if quantity <= 0:
            continue
        price = final_price(product)
        items.append(
            {
                "product_id": product.id,
                "slug": product.slug,
                "title": product.title,
                "unit": product.unit,
                "price": float(price),
                "quantity": float(quantity),
                "image_url": product.image_url or "",
            }
        )
        total += price * quantity
    return items, money(total)


def sync(db: Session, payload, user: User | None) -> dict:
    """Сохраняет текущую корзину. Пустая корзина удаляет запись."""
    cart = db.scalar(select(Cart).where(Cart.session_key == payload.session_key))
    items, total = _cart_items(db, payload)
    if not items:
        if cart:
            db.delete(cart)
        return {"stored": False, "items": 0}

    if cart is None:
        cart = Cart(
            session_key=payload.session_key,
            items=[],
            last_activity_at=_now(),
        )
        db.add(cart)

    phone = ""
    if payload.phone.strip():
        try:
            phone = normalize_phone(payload.phone)
        except ValueError:
            phone = ""
    email = payload.email.strip().lower()
    if email and ("@" not in email or "." not in email.split("@")[-1]):
        email = ""

    cart.items = items
    cart.items_count = len(items)
    cart.total = total
    cart.status = "active"
    cart.last_activity_at = _now()
    if payload.name.strip():
        cart.name = payload.name.strip()[:120]
    if phone:
        cart.phone = phone
    if email:
        cart.email = email
    if user:
        cart.user_id = user.id
        cart.name = cart.name or user.full_name or ""
        cart.phone = cart.phone or user.phone or ""
        cart.email = cart.email or (user.email or "").lower()
    db.flush()
    return {"stored": True, "items": len(items), "total": float(total)}


def mark_converted(db: Session, phone: str = "", user_id: int | None = None) -> int:
    """Помечает корзины покупателя оформленными после создания заказа."""
    stmt = select(Cart).where(Cart.status == "active")
    if user_id:
        stmt = stmt.where(Cart.user_id == user_id)
    elif phone:
        stmt = stmt.where(Cart.phone == phone)
    else:
        return 0
    carts = db.scalars(stmt).all()
    for cart in carts:
        cart.status = "converted"
    return len(carts)


def is_abandoned(cart: Cart, now: datetime | None = None) -> bool:
    if cart.status != "active" or not cart.items:
        return False
    moment = now or _now()
    last = cart.last_activity_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return last <= moment - timedelta(minutes=ABANDON_MINUTES)


def serialize(cart: Cart, now: datetime | None = None) -> dict:
    return {
        "id": cart.id,
        "name": cart.name or "Гость",
        "phone": format_phone(cart.phone) if cart.phone else "",
        "phone_raw": cart.phone,
        "email": cart.email,
        "items": cart.items or [],
        "items_count": cart.items_count,
        "total": float(cart.total or 0),
        "status": cart.status,
        "abandoned": is_abandoned(cart, now),
        "reminder_count": cart.reminder_count,
        "reminded_at": cart.reminded_at,
        "last_activity_at": cart.last_activity_at,
        "created_at": cart.created_at,
    }


def admin_list(db: Session, status: str = "abandoned", limit: int = 100) -> dict:
    now = _now()
    rows = db.scalars(
        select(Cart).order_by(Cart.last_activity_at.desc()).limit(max(limit * 4, 200))
    ).all()
    items = []
    for cart in rows:
        abandoned = is_abandoned(cart, now)
        if status == "abandoned" and not abandoned:
            continue
        if status == "active" and cart.status != "active":
            continue
        if status == "converted" and cart.status != "converted":
            continue
        items.append(serialize(cart, now))
        if len(items) >= limit:
            break
    abandoned_carts = [row for row in rows if is_abandoned(row, now)]
    return {
        "items": items,
        "total": len(items),
        "summary": {
            "abandoned": len(abandoned_carts),
            "abandoned_value": float(sum((cart.total or 0) for cart in abandoned_carts)),
            "with_contact": sum(1 for cart in abandoned_carts if cart.email or cart.phone),
            "active": sum(1 for cart in rows if cart.status == "active"),
        },
        "threshold_minutes": ABANDON_MINUTES,
    }


def _message(cart: Cart, brand: str, link: str) -> tuple[str, str]:
    titles = [item.get("title", "") for item in (cart.items or [])][:3]
    rest = max(0, len(cart.items or []) - len(titles))
    listing = ", ".join(title for title in titles if title)
    if rest:
        listing = f"{listing} и ещё {rest}"
    total = f"{float(cart.total or 0):.2f} BYN".replace(".", ",")
    name = cart.name or "друг"
    text = (
        f"Здравствуйте, {name}!\n\n"
        f"В корзине {brand} остались товары на {total}: {listing}.\n"
        f"Вернитесь, чтобы завершить заказ: {link}\n\n"
        f"Если передумали — просто пропустите это сообщение."
    )
    subject = f"Ваша корзина в {brand}"
    return text, subject


def remind(db: Session, cart: Cart) -> dict:
    if cart.status != "active":
        raise HTTPException(status_code=400, detail="Корзина уже не активна")
    if not cart.items:
        raise HTTPException(status_code=400, detail="Корзина пустая")
    if cart.reminded_at:
        last = cart.reminded_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last > _now() - timedelta(hours=REMIND_COOLDOWN_HOURS):
            raise HTTPException(
                status_code=409,
                detail="Напоминание уже отправляли меньше суток назад",
            )
    if cart.user_id:
        user = db.get(User, cart.user_id)
        if user is not None and not user.consent_personal_data:
            raise HTTPException(status_code=400, detail="Клиент не давал согласия на рассылку")

    channel = "email" if cart.email else ("sms" if cart.phone else "")
    if not channel:
        raise HTTPException(status_code=400, detail="Нет почты или телефона для напоминания")
    ready = channels_status().get(channel, False)
    demo = settings.demo_mode and not ready
    if not ready and not demo:
        hint = "Настройте SMTP" if channel == "email" else "Подключите SMS-провайдера"
        raise HTTPException(status_code=400, detail=f"Канал не настроен. {hint}.")

    conf = get_settings_model(db)
    brand = conf.brand_name
    link = f"{settings.public_base_url.rstrip('/')}/cart"
    text, subject = _message(cart, brand, link)
    try:
        if not demo:
            if channel == "email":
                send_email(cart.email, subject, text)
            else:
                send_sms(cart.phone, text[:480])
    except (RuntimeError, OSError, SmsError, ValueError) as exc:
        log.warning("Напоминание о корзине %s не отправлено: %s", cart.id, exc)
        raise HTTPException(status_code=502, detail=f"Не удалось отправить: {exc}") from exc

    cart.reminder_count += 1
    cart.reminded_at = _now()
    db.flush()
    return {
        "sent": True,
        "demo": demo,
        "channel": channel,
        "contact": cart.email if channel == "email" else format_phone(cart.phone),
        "cart": serialize(cart),
    }


def remind_all(db: Session) -> dict:
    now = _now()
    carts = db.scalars(
        select(Cart)
        .where(Cart.status == "active")
        .order_by(Cart.last_activity_at.desc())
        .limit(500)
    ).all()
    sent = demo = skipped = failed = 0
    errors: list[str] = []
    for cart in carts:
        if not is_abandoned(cart, now):
            continue
        if not (cart.email or cart.phone):
            skipped += 1
            continue
        if cart.reminded_at:
            last = cart.reminded_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if last > now - timedelta(hours=REMIND_COOLDOWN_HOURS):
                skipped += 1
                continue
        try:
            result = remind(db, cart)
            sent += 1
            if result.get("demo"):
                demo += 1
        except HTTPException as exc:
            failed += 1
            if len(errors) < 5:
                errors.append(str(exc.detail))
        if sent + failed >= MAX_REMINDERS_PER_RUN:
            break
    return {
        "sent": sent,
        "demo": demo,
        "skipped": skipped,
        "failed": failed,
        "errors": errors,
    }


def dismiss(db: Session, cart: Cart) -> None:
    db.delete(cart)
