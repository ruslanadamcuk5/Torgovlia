"""Склад: движение остатков и история операций."""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Product, StockMovement
from app.utils import qty


KIND_IN = "in"
KIND_OUT = "out"
KIND_ADJUST = "adjust"
KIND_ORDER = "order"
KIND_CANCEL = "cancel"

KIND_LABELS = {
    KIND_IN: "Приход",
    KIND_OUT: "Списание",
    KIND_ADJUST: "Инвентаризация",
    KIND_ORDER: "Заказ",
    KIND_CANCEL: "Отмена заказа",
}

DEFAULT_REASON = {
    KIND_IN: "Поступление товара",
    KIND_OUT: "Списание",
    KIND_ADJUST: "Инвентаризация",
}


def serialize(movement: StockMovement) -> dict:
    return {
        "id": movement.id,
        "product_id": movement.product_id,
        "product_title": movement.product_title,
        "kind": movement.kind,
        "kind_label": KIND_LABELS.get(movement.kind, movement.kind),
        "quantity": float(movement.quantity),
        "stock_before": float(movement.stock_before),
        "stock_after": float(movement.stock_after),
        "reason": movement.reason,
        "actor": movement.actor,
        "created_at": movement.created_at,
    }


def _record(
    db: Session,
    product: Product,
    *,
    kind: str,
    delta: Decimal,
    before: Decimal,
    after: Decimal,
    reason: str,
    actor: str,
) -> StockMovement:
    movement = StockMovement(
        product_id=product.id,
        product_title=product.title,
        kind=kind,
        quantity=delta,
        stock_before=before,
        stock_after=after,
        reason=reason[:200],
        actor=actor[:120],
    )
    db.add(movement)
    return movement


def record_order(
    db: Session,
    product: Product,
    quantity: Decimal,
    number: str,
    actor: str = "client",
) -> None:
    """Списание по брони. Остаток уже уменьшен вызывающим кодом."""
    after = Decimal(product.stock or 0)
    _record(
        db,
        product,
        kind=KIND_ORDER,
        delta=-Decimal(quantity),
        before=qty(after + Decimal(quantity)),
        after=qty(after),
        reason=f"Бронь {number}",
        actor=actor,
    )


def record_cancel(
    db: Session,
    product: Product,
    quantity: Decimal,
    number: str,
    actor: str,
) -> None:
    """Возврат остатка при отмене. Остаток уже увеличен вызывающим кодом."""
    after = Decimal(product.stock or 0)
    _record(
        db,
        product,
        kind=KIND_CANCEL,
        delta=Decimal(quantity),
        before=qty(after - Decimal(quantity)),
        after=qty(after),
        reason=f"Отмена {number}",
        actor=actor,
    )


def apply_move(
    db: Session,
    product: Product,
    *,
    kind: str,
    quantity: float,
    reason: str,
    actor: str,
) -> StockMovement:
    """Ручная операция: приход, списание или установка фактического остатка."""
    amount = qty(Decimal(str(quantity)))
    if amount < 0:
        raise HTTPException(status_code=400, detail="Количество не может быть отрицательным")

    before = Decimal(product.stock or 0)
    if kind == KIND_IN:
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Укажите количество для прихода")
        after = qty(before + amount)
        delta = amount
    elif kind == KIND_OUT:
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Укажите количество для списания")
        if product.stock is None:
            raise HTTPException(status_code=400, detail="У товара не ведётся учёт остатка")
        if amount > before:
            unit = "кг" if product.unit == "kg" else "шт."
            raise HTTPException(
                status_code=400,
                detail=f"На складе только {float(before):g} {unit}",
            )
        after = qty(before - amount)
        delta = -amount
    elif kind == KIND_ADJUST:
        after = amount
        delta = qty(after - before)
    else:
        raise HTTPException(status_code=400, detail="Неизвестная операция склада")

    product.stock = after
    return _record(
        db,
        product,
        kind=kind,
        delta=delta,
        before=qty(before),
        after=qty(after),
        reason=reason.strip() or DEFAULT_REASON.get(kind, ""),
        actor=actor,
    )
