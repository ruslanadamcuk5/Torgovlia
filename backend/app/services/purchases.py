"""Поставщики и закупки: карточки, заявки и приёмка на склад."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    PURCHASE_CANCELLED,
    PURCHASE_DRAFT,
    PURCHASE_ORDERED,
    PURCHASE_RECEIVED,
    Product,
    PurchaseItem,
    PurchaseOrder,
    Supplier,
)
from app.schemas import PurchaseIn
from app.services.inventory import KIND_IN, apply_move
from app.tenancy import tenant_get
from app.utils import local_now, money, qty


STATUS_LABELS = {
    PURCHASE_DRAFT: "Черновик",
    PURCHASE_ORDERED: "Заказано",
    PURCHASE_RECEIVED: "Принято",
    PURCHASE_CANCELLED: "Отменено",
}


def serialize_supplier(supplier: Supplier) -> dict:
    return {
        "id": supplier.id,
        "name": supplier.name,
        "contact_person": supplier.contact_person,
        "phone": supplier.phone,
        "email": supplier.email,
        "address": supplier.address,
        "note": supplier.note,
        "is_active": bool(supplier.is_active),
        "created_at": supplier.created_at,
        "updated_at": supplier.updated_at,
    }


def serialize_purchase(purchase: PurchaseOrder) -> dict:
    return {
        "id": purchase.id,
        "number": purchase.number,
        "supplier_id": purchase.supplier_id,
        "supplier_name": purchase.supplier_name,
        "status": purchase.status,
        "status_label": STATUS_LABELS.get(purchase.status, purchase.status),
        "expected_date": purchase.expected_date,
        "received_at": purchase.received_at,
        "total_amount": float(purchase.total_amount or 0),
        "note": purchase.note,
        "created_at": purchase.created_at,
        "updated_at": purchase.updated_at,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "title": item.title,
                "unit": item.unit,
                "quantity": float(item.quantity or 0),
                "cost": float(item.cost or 0),
                "line_total": float(item.line_total or 0),
            }
            for item in purchase.items
        ],
    }


def _next_number(db: Session) -> str:
    prefix = local_now().strftime("%y%m%d")
    for _ in range(20):
        candidate = f"PO-{prefix}-{secrets.randbelow(9000) + 1000}"
        exists = db.scalar(
            select(PurchaseOrder.id)
            .where(PurchaseOrder.number == candidate)
            .execution_options(skip_tenant_filter=True)
        )
        if not exists:
            return candidate
    return f"PO-{prefix}-{secrets.token_hex(3).upper()}"


def create_purchase(db: Session, payload: PurchaseIn) -> PurchaseOrder:
    supplier = tenant_get(db, Supplier, payload.supplier_id) if payload.supplier_id else None
    if payload.supplier_id and not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")

    purchase = PurchaseOrder(
        number=_next_number(db),
        supplier_id=supplier.id if supplier else None,
        supplier_name=supplier.name if supplier else "",
        status=PURCHASE_DRAFT,
        expected_date=payload.expected_date,
        note=payload.note.strip(),
        total_amount=Decimal("0.00"),
    )

    total = Decimal("0.00")
    for row in payload.items:
        product = tenant_get(db, Product, row.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Один из товаров не найден")
        quantity = qty(Decimal(str(row.quantity)))
        cost = money(Decimal(str(row.cost)))
        line_total = money(cost * quantity)
        total += line_total
        purchase.items.append(
            PurchaseItem(
                product_id=product.id,
                title=product.title,
                unit=product.unit,
                quantity=quantity,
                cost=cost,
                line_total=line_total,
            )
        )

    purchase.total_amount = money(total)
    db.add(purchase)
    db.flush()
    return purchase


def transition_purchase(db: Session, purchase: PurchaseOrder, status: str, actor: str) -> PurchaseOrder:
    if status == PURCHASE_RECEIVED:
        return receive_purchase(db, purchase, actor)
    if status == purchase.status:
        return purchase
    if purchase.status == PURCHASE_RECEIVED:
        raise HTTPException(status_code=400, detail="Принятую закупку нельзя изменить")
    if status not in (PURCHASE_DRAFT, PURCHASE_ORDERED, PURCHASE_CANCELLED):
        raise HTTPException(status_code=400, detail="Неизвестный статус закупки")
    purchase.status = status
    if status == PURCHASE_CANCELLED:
        purchase.received_at = None
    return purchase


def receive_purchase(db: Session, purchase: PurchaseOrder, actor: str) -> PurchaseOrder:
    if purchase.status == PURCHASE_RECEIVED:
        raise HTTPException(status_code=400, detail="Закупка уже принята")
    if purchase.status == PURCHASE_CANCELLED:
        raise HTTPException(status_code=400, detail="Отменённую закупку нельзя принять")

    for item in purchase.items:
        if not item.product_id:
            continue
        product = tenant_get(db, Product, item.product_id)
        if not product:
            continue
        apply_move(
            db,
            product,
            kind=KIND_IN,
            quantity=float(item.quantity),
            reason=f"Закупка {purchase.number}",
            actor=actor,
        )

    purchase.status = PURCHASE_RECEIVED
    purchase.received_at = datetime.now(timezone.utc)
    return purchase
