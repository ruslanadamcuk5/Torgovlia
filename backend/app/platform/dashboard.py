"""Сводка платформы: выручка, рост, оплаты и состояние портфеля магазинов."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    TENANT_ACTIVE,
    TENANT_ARCHIVED,
    TENANT_GRACE,
    TENANT_ONBOARDING,
    TENANT_SUSPENDED,
    Invoice,
    Tenant,
    TenantService,
)
from app.platform.catalog import PLAN_BY_CODE, SERVICE_BY_CODE, included_in_plan
from app.platform.ops import latest_job, tenant_health, JOB_IN_PROGRESS, JOB_QUEUED


def _money(value) -> Decimal:  # noqa: ANN001
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _monthly_price(tenant: Tenant) -> Decimal:
    plan = PLAN_BY_CODE.get(tenant.plan_code)
    return _money(plan.price_month) if plan else Decimal("0.00")


def mrr(db: Session) -> dict:
    """Месячная выручка по активным подпискам и подключённым add-on."""
    tenants = db.scalars(
        select(Tenant)
        .where(Tenant.status.in_((TENANT_ACTIVE, TENANT_GRACE)))
        .execution_options(skip_tenant_filter=True)
    ).all()
    plans_total = Decimal("0.00")
    addons_total = Decimal("0.00")
    addon_rows = db.scalars(
        select(TenantService)
        .where(TenantService.status == "enabled")
        .execution_options(skip_tenant_filter=True)
    ).all()
    tenant_map = {tenant.id: tenant for tenant in tenants}
    for row in addon_rows:
        tenant = tenant_map.get(row.tenant_id)
        if not tenant:
            continue
        definition = SERVICE_BY_CODE.get(row.service_code)
        if not definition or definition.price_month <= 0:
            continue
        if included_in_plan(row.service_code, tenant.plan_code):
            continue
        addons_total += _money(definition.price_month)
    for tenant in tenants:
        plans_total += _monthly_price(tenant)
    total = plans_total + addons_total
    return {
        "mrr": float(total),
        "mrr_plans": float(plans_total),
        "mrr_addons": float(addons_total),
        "arr": float(total * 12),
        "paying_tenants": len(tenants),
    }


def overview(db: Session) -> dict:
    now = datetime.now(timezone.utc)
    month_ago = now - timedelta(days=30)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    tenants = db.scalars(
        select(Tenant).execution_options(skip_tenant_filter=True)
    ).all()
    by_status: dict[str, int] = {}
    for tenant in tenants:
        by_status[tenant.status] = by_status.get(tenant.status, 0) + 1

    new_30d = sum(1 for tenant in tenants if tenant.created_at and tenant.created_at >= month_ago)
    revenue = mrr(db)

    paid_30d = db.scalar(
        select(func.coalesce(func.sum(Invoice.amount), 0)).where(
            Invoice.status == "paid", Invoice.paid_at >= month_ago
        )
    )
    paid_month = db.scalar(
        select(func.coalesce(func.sum(Invoice.amount), 0)).where(
            Invoice.status == "paid", Invoice.paid_at >= start_of_month
        )
    )
    open_total = db.scalar(
        select(func.coalesce(func.sum(Invoice.amount), 0)).where(Invoice.status == "open")
    )
    open_count = db.scalar(select(func.count(Invoice.id)).where(Invoice.status == "open"))

    health_items = []
    queue = 0
    attention = 0
    for tenant in tenants:
        job = latest_job(db, tenant.id)
        item = tenant_health(db, tenant, job)
        if item["level"] != "ok":
            attention += 1
        if job and job.status in (JOB_QUEUED, JOB_IN_PROGRESS):
            queue += 1
        health_items.append(item)

    return {
        "tenants_total": len(tenants),
        "tenants_active": by_status.get(TENANT_ACTIVE, 0),
        "tenants_onboarding": by_status.get(TENANT_ONBOARDING, 0),
        "tenants_suspended": by_status.get(TENANT_SUSPENDED, 0),
        "tenants_archived": by_status.get(TENANT_ARCHIVED, 0),
        "new_30d": new_30d,
        "mrr": revenue["mrr"],
        "mrr_plans": revenue["mrr_plans"],
        "mrr_addons": revenue["mrr_addons"],
        "arr": revenue["arr"],
        "paying_tenants": revenue["paying_tenants"],
        "paid_30d": float(_money(paid_30d)),
        "paid_month": float(_money(paid_month)),
        "open_invoices_total": float(_money(open_total)),
        "open_invoices_count": int(open_count or 0),
        "queue_total": queue,
        "attention_total": attention,
        "by_status": by_status,
    }
