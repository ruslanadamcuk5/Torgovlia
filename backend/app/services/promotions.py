"""Промокоды магазина: проверка, расчёт скидки и списание использования."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PromoCode
from app.utils import money


def normalize_code(code: str | None) -> str:
    return (code or "").strip().upper()


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def status_of(promo: PromoCode, now: datetime | None = None) -> str:
    moment = now or datetime.now(timezone.utc)
    if not promo.is_active:
        return "disabled"
    starts = _aware(promo.starts_at)
    ends = _aware(promo.ends_at)
    if starts and starts > moment:
        return "scheduled"
    if ends and ends < moment:
        return "expired"
    if promo.max_uses and promo.used_count >= promo.max_uses:
        return "used_up"
    return "active"


def find_promo(db: Session, code: str | None) -> PromoCode | None:
    normalized = normalize_code(code)
    if not normalized:
        return None
    return db.scalar(select(PromoCode).where(PromoCode.code == normalized))


def discount_for(promo: PromoCode, subtotal: Decimal) -> Decimal:
    if promo.kind == "percent":
        raw = subtotal * Decimal(str(promo.value)) / Decimal("100")
    else:
        raw = Decimal(str(promo.value))
    return money(min(raw, subtotal))


def resolve(db: Session, code: str | None, subtotal: Decimal) -> tuple[PromoCode, Decimal, Decimal]:
    """Возвращает промокод, скидку и итог или понятную ошибку 400."""
    normalized = normalize_code(code)
    if not normalized:
        raise HTTPException(status_code=400, detail="Введите промокод")
    promo = find_promo(db, normalized)
    if not promo:
        raise HTTPException(status_code=400, detail="Промокод не найден. Проверьте написание.")

    state = status_of(promo)
    if state == "disabled":
        raise HTTPException(status_code=400, detail="Промокод больше не действует")
    if state == "scheduled":
        raise HTTPException(status_code=400, detail="Промокод ещё не начал действовать")
    if state == "expired":
        raise HTTPException(status_code=400, detail="Срок действия промокода истёк")
    if state == "used_up":
        raise HTTPException(status_code=400, detail="Лимит использований промокода исчерпан")

    minimum = Decimal(str(promo.min_order or 0))
    if subtotal < minimum:
        raise HTTPException(
            status_code=400,
            detail=f"Промокод действует от {minimum:.2f} BYN".replace(".", ","),
        )

    discount = discount_for(promo, subtotal)
    if discount <= 0:
        raise HTTPException(status_code=400, detail="Промокод не даёт скидку на этот заказ")
    return promo, discount, money(subtotal - discount)


def redeem(promo: PromoCode) -> None:
    """Списывает одно использование. Коммит делает вызывающий заказ."""
    promo.used_count = int(promo.used_count or 0) + 1


def serialize(promo: PromoCode) -> dict:
    return {
        "id": promo.id,
        "code": promo.code,
        "kind": promo.kind,
        "value": float(promo.value or 0),
        "min_order": float(promo.min_order or 0),
        "max_uses": int(promo.max_uses or 0),
        "used_count": int(promo.used_count or 0),
        "starts_at": promo.starts_at,
        "ends_at": promo.ends_at,
        "is_active": bool(promo.is_active),
        "note": promo.note or "",
        "status": status_of(promo),
        "created_at": promo.created_at,
        "updated_at": promo.updated_at,
    }
