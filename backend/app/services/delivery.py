"""Доставка: зоны, минимальная сумма и стоимость."""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DeliveryZone
from app.platform.sync import is_enabled
from app.tenancy import current_tenant, tenant_get
from app.utils import money


def feature_enabled(db: Session) -> bool:
    tenant = current_tenant()
    return bool(tenant and is_enabled(db, tenant.id, "delivery"))


def zones(db: Session, active_only: bool = True) -> list[DeliveryZone]:
    stmt = select(DeliveryZone).order_by(DeliveryZone.sort_order.asc(), DeliveryZone.name.asc())
    if active_only:
        stmt = stmt.where(DeliveryZone.is_active.is_(True))
    return list(db.scalars(stmt).all())


def serialize(zone: DeliveryZone, subtotal: Decimal | None = None) -> dict:
    fee = Decimal(str(zone.fee or 0))
    if subtotal is not None and zone.free_from and subtotal >= Decimal(str(zone.free_from)):
        fee = Decimal("0.00")
    return {
        "id": zone.id,
        "name": zone.name,
        "areas": zone.areas or "",
        "fee": float(money(fee)),
        "min_order": float(zone.min_order or 0),
        "free_from": float(zone.free_from or 0),
        "eta": zone.eta or "",
        "is_active": bool(zone.is_active),
        "sort_order": int(zone.sort_order or 0),
    }


def resolve(db: Session, zone_id: int | None, subtotal: Decimal) -> tuple[DeliveryZone, Decimal]:
    if not zone_id:
        raise HTTPException(status_code=400, detail="Выберите зону доставки")
    zone = tenant_get(db, DeliveryZone, zone_id)
    if not zone or not zone.is_active:
        raise HTTPException(status_code=400, detail="Эта зона доставки недоступна")

    minimum = Decimal(str(zone.min_order or 0))
    if subtotal < minimum:
        raise HTTPException(
            status_code=400,
            detail=f"Минимальная сумма доставки в зону «{zone.name}» — {minimum:.2f} BYN".replace(".", ","),
        )

    fee = Decimal(str(zone.fee or 0))
    free_from = Decimal(str(zone.free_from or 0))
    if free_from and subtotal >= free_from:
        fee = Decimal("0.00")
    return zone, money(fee)
