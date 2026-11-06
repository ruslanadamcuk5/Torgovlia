"""Счета и подписки: ручной/ассистируемый биллинг.

На этом этапе платформа выставляет счёт, а оплата подтверждается вручную в
панели платформы. Позже сюда подключаются платёжные провайдеры (bePaid, ЕРИП,
hoster.by) через адаптеры — модель счетов остаётся той же.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Invoice, Plan, Subscription, Tenant
from app.platform.catalog import PLAN_BY_CODE, SERVICE_CATALOG, included_in_plan
from app.platform.sync import _service_row, _subscription, ensure_tenant_services


INVOICE_OPEN = "open"
INVOICE_PAID = "paid"
INVOICE_CANCELED = "canceled"
INVOICE_DRAFT = "draft"
INVOICE_STATUSES = (INVOICE_DRAFT, INVOICE_OPEN, INVOICE_PAID, INVOICE_CANCELED)

KIND_SUBSCRIPTION = "subscription"
KIND_PLAN_CHANGE = "plan_change"
KIND_ADDON = "addon"
KIND_MANUAL = "manual"


def now() -> datetime:
    return datetime.now(timezone.utc)


def _price(value) -> Decimal:  # noqa: ANN001
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def plan_price(db: Session, plan_code: str) -> Decimal:
    plan = db.get(Plan, plan_code)
    if not plan:
        raise HTTPException(status_code=422, detail="Неизвестный тариф")
    return _price(plan.price_month)


def current_plan(db: Session, tenant: Tenant) -> str:
    subscription = _subscription(db, tenant.id)
    return (subscription.plan_code if subscription else None) or tenant.plan_code


def create_invoice(
    db: Session,
    tenant: Tenant,
    *,
    kind: str,
    amount: Decimal | float | int,
    description: str,
    plan_code: str | None = None,
    service_code: str | None = None,
    period_days: int = 30,
    due_days: int = 14,
    note: str = "",
) -> Invoice:
    start = now()
    invoice = Invoice(
        tenant_id=tenant.id,
        number="",
        kind=kind,
        status=INVOICE_OPEN,
        plan_code=plan_code,
        service_code=service_code,
        description=description,
        amount=_price(amount),
        currency=tenant.currency or "BYN",
        period_start=start,
        period_end=start + timedelta(days=period_days) if period_days else None,
        due_at=start + timedelta(days=due_days),
        note=note,
    )
    db.add(invoice)
    db.flush()
    invoice.number = f"INV-{start:%Y%m}-{invoice.id:05d}"
    db.commit()
    db.refresh(invoice)
    return invoice


def invoice_payload(invoice: Invoice) -> dict:
    return {
        "id": invoice.id,
        "number": invoice.number,
        "kind": invoice.kind,
        "status": invoice.status,
        "plan_code": invoice.plan_code,
        "service_code": invoice.service_code,
        "description": invoice.description,
        "amount": float(invoice.amount or 0),
        "currency": invoice.currency,
        "period_start": invoice.period_start,
        "period_end": invoice.period_end,
        "due_at": invoice.due_at,
        "paid_at": invoice.paid_at,
        "payment_method": invoice.payment_method,
        "note": invoice.note,
        "created_at": invoice.created_at,
    }


def list_invoices(db: Session, tenant_id: int, limit: int = 100) -> list[Invoice]:
    return list(
        db.scalars(
            select(Invoice)
            .where(Invoice.tenant_id == tenant_id)
            .order_by(Invoice.created_at.desc())
            .limit(limit)
            .execution_options(skip_tenant_filter=True)
        ).all()
    )


def _apply_plan(db: Session, tenant: Tenant, plan_code: str) -> Subscription:
    if plan_code not in PLAN_BY_CODE:
        raise HTTPException(status_code=422, detail="Неизвестный тариф")
    subscription = _subscription(db, tenant.id)
    old_plan = (subscription.plan_code if subscription else None) or tenant.plan_code
    start = now()
    if not subscription:
        subscription = Subscription(
            tenant_id=tenant.id,
            plan_code=plan_code,
            status="active",
            period_start=start,
            period_end=start + timedelta(days=30),
        )
        db.add(subscription)
    else:
        subscription.plan_code = plan_code
        subscription.pending_plan_code = None
        subscription.status = "active"
        subscription.period_start = start
        subscription.period_end = start + timedelta(days=30)
    tenant.plan_code = plan_code
    ensure_tenant_services(db, tenant)

    # Сервисы, которые впервые появляются в новом тарифе, включаем по умолчанию.
    # Ранее доступные сервисы не трогаем: владелец мог выключить их сам.
    for definition in SERVICE_CATALOG:
        if not definition.default_enabled:
            continue
        if not included_in_plan(definition.code, plan_code):
            continue
        if included_in_plan(definition.code, old_plan):
            continue
        row = _service_row(db, tenant.id, definition.code)
        if not row or row.locked_by_platform:
            continue
        if row.status in ("disabled", "pending_payment") and row.source in ("none", "plan"):
            row.status = "enabled"
            row.source = "plan"
            row.enabled_at = row.enabled_at or start
            row.disabled_at = None
    db.commit()
    db.refresh(subscription)
    return subscription


def mark_paid(
    db: Session,
    invoice: Invoice,
    *,
    method: str = "manual",
    external_id: str | None = None,
    actor: str = "",
) -> Invoice:
    if invoice.status == INVOICE_PAID:
        return invoice
    if invoice.status == INVOICE_CANCELED:
        raise HTTPException(status_code=409, detail="Счёт отменён")
    tenant = db.scalar(
        select(Tenant)
        .where(Tenant.id == invoice.tenant_id)
        .execution_options(skip_tenant_filter=True)
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Арендатор не найден")

    invoice.status = INVOICE_PAID
    invoice.paid_at = now()
    invoice.payment_method = method
    invoice.external_id = external_id

    if invoice.plan_code:
        _apply_plan(db, tenant, invoice.plan_code)
    if invoice.service_code:
        ensure_tenant_services(db, tenant)
        row = _service_row(db, tenant.id, invoice.service_code)
        if row:
            row.status = "enabled"
            row.source = "addon" if invoice.kind == KIND_ADDON else "paid"
            row.enabled_at = row.enabled_at or now()
            row.disabled_at = None

    db.commit()
    db.refresh(invoice)
    return invoice


def cancel_invoice(db: Session, invoice: Invoice, reason: str = "") -> Invoice:
    if invoice.status == INVOICE_PAID:
        raise HTTPException(status_code=409, detail="Оплаченный счёт нельзя отменить")
    invoice.status = INVOICE_CANCELED
    if reason:
        invoice.note = f"{invoice.note}\n{reason}".strip()
    if invoice.service_code:
        row = _service_row(db, invoice.tenant_id, invoice.service_code)
        if row and row.status == "pending_payment":
            row.status = "disabled"
    db.commit()
    db.refresh(invoice)
    return invoice


def request_plan(db: Session, tenant: Tenant, plan_code: str) -> dict:
    """Смена тарифа: понижение сразу, повышение — после оплаты счёта."""
    if plan_code not in PLAN_BY_CODE:
        raise HTTPException(status_code=422, detail="Неизвестный тариф")
    current = current_plan(db, tenant)
    if current == plan_code:
        return {"applied": False, "reason": "same_plan", "plan_code": current}

    old_price = plan_price(db, current) if current in PLAN_BY_CODE else Decimal("0")
    new_price = plan_price(db, plan_code)
    if new_price <= old_price:
        _apply_plan(db, tenant, plan_code)
        db.commit()
        return {"applied": True, "plan_code": plan_code, "invoice": None}

    subscription = _subscription(db, tenant.id)
    if subscription:
        subscription.pending_plan_code = plan_code
        db.commit()
    invoice = create_invoice(
        db,
        tenant,
        kind=KIND_PLAN_CHANGE,
        amount=new_price,
        description=f"Смена тарифа на «{PLAN_BY_CODE[plan_code].title}»",
        plan_code=plan_code,
    )
    return {"applied": False, "plan_code": current, "pending_plan_code": plan_code, "invoice": invoice_payload(invoice)}


def pending_addon_invoice(db: Session, tenant: Tenant, service_code: str) -> Invoice | None:
    return db.scalar(
        select(Invoice)
        .where(
            Invoice.tenant_id == tenant.id,
            Invoice.service_code == service_code,
            Invoice.status == INVOICE_OPEN,
        )
        .execution_options(skip_tenant_filter=True)
    )


def billing_overview(db: Session, tenant: Tenant) -> dict:
    subscription = _subscription(db, tenant.id)
    plan_code = (subscription.plan_code if subscription else None) or tenant.plan_code
    plan = db.get(Plan, plan_code)
    open_total = db.scalar(
        select(func.coalesce(func.sum(Invoice.amount), 0)).where(
            Invoice.tenant_id == tenant.id, Invoice.status == INVOICE_OPEN
        ).execution_options(skip_tenant_filter=True)
    )
    return {
        "plan_code": plan_code,
        "plan_title": plan.title if plan else plan_code,
        "price_month": float(plan.price_month) if plan else 0,
        "subscription_status": subscription.status if subscription else "active",
        "period_end": subscription.period_end if subscription else None,
        "pending_plan_code": subscription.pending_plan_code if subscription else None,
        "open_invoices_total": float(open_total or 0),
        "invoices": [invoice_payload(item) for item in list_invoices(db, tenant.id)],
    }
