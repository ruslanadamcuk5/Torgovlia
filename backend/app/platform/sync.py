"""Синхронизация реестра сервисов и выдача entitlements арендаторам."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Plan, PlanService, Service, Subscription, Tenant, TenantService
from app.platform.catalog import (
    PLANS,
    SERVICE_CATALOG,
    TIER_ADDON,
    TIER_FREE,
    TIER_PLATFORM,
    included_in_plan,
)


log = logging.getLogger("torgovlia.services")


def sync_catalog(db: Session) -> None:
    """Идемпотентно обновляет services/plans/plan_services из кода."""
    for definition in SERVICE_CATALOG:
        service = db.get(Service, definition.code)
        if not service:
            service = Service(code=definition.code)
            db.add(service)
        service.title = definition.title
        service.group = definition.group
        service.description = definition.description
        service.tier = definition.tier
        service.price_month = definition.price_month
        service.dependencies = list(definition.dependencies)
        service.default_enabled = definition.default_enabled
        service.trial_days = definition.trial_days
        service.sort_order = definition.sort_order
        service.icon = definition.icon
        service.config_schema = definition.config_schema
        service.is_active = True

    for definition in PLANS:
        plan = db.get(Plan, definition.code)
        if not plan:
            plan = Plan(code=definition.code)
            db.add(plan)
        plan.title = definition.title
        plan.description = definition.description
        plan.price_month = definition.price_month
        plan.price_year = definition.price_year
        plan.quotas = definition.quotas
        plan.sort_order = definition.sort_order
        plan.is_active = True

    db.flush()

    for plan in PLANS:
        for definition in SERVICE_CATALOG:
            row = db.get(PlanService, (plan.code, definition.code))
            included = included_in_plan(definition.code, plan.code)
            if not row:
                db.add(
                    PlanService(
                        plan_code=plan.code,
                        service_code=definition.code,
                        included=included,
                    )
                )
            else:
                row.included = included

    db.commit()
    log.info("Реестр сервисов синхронизирован: %s сервисов", len(SERVICE_CATALOG))


def _subscription(db: Session, tenant_id: int) -> Subscription | None:
    return db.scalar(
        select(Subscription)
        .where(Subscription.tenant_id == tenant_id)
        .execution_options(skip_tenant_filter=True)
    )


def _service_row(db: Session, tenant_id: int, code: str) -> TenantService | None:
    return db.scalar(
        select(TenantService)
        .where(TenantService.tenant_id == tenant_id, TenantService.service_code == code)
        .execution_options(skip_tenant_filter=True)
    )


def ensure_tenant_services(db: Session, tenant: Tenant, trial_days: int = 14) -> Subscription:
    """Создаёт подписку и строки сервисов, если их ещё нет."""
    now = datetime.now(timezone.utc)
    subscription = _subscription(db, tenant.id)
    if not subscription:
        subscription = Subscription(
            tenant_id=tenant.id,
            plan_code=tenant.plan_code,
            status="trial",
            period_start=now,
            period_end=now + timedelta(days=trial_days),
            trial_ends_at=now + timedelta(days=trial_days),
        )
        db.add(subscription)
        db.flush()

    plan_code = subscription.plan_code or tenant.plan_code
    for definition in SERVICE_CATALOG:
        row = _service_row(db, tenant.id, definition.code)
        included = included_in_plan(definition.code, plan_code)
        if not row:
            enabled = included and definition.default_enabled
            db.add(
                TenantService(
                    tenant_id=tenant.id,
                    service_code=definition.code,
                    status="enabled" if enabled else "disabled",
                    source="plan" if included else "none",
                    enabled_at=now if enabled else None,
                )
            )
        elif row.source == "plan" and not included and row.status in ("enabled", "trial"):
            row.status = "disabled"
            row.disabled_at = now
    db.commit()
    return subscription


def plan_for_tenant(db: Session, tenant_id: int) -> str:
    subscription = _subscription(db, tenant_id)
    if subscription:
        return subscription.plan_code
    tenant = db.scalar(
        select(Tenant).where(Tenant.id == tenant_id).execution_options(skip_tenant_filter=True)
    )
    return tenant.plan_code if tenant else "start"


def is_enabled(db: Session, tenant_id: int, code: str) -> bool:
    row = _service_row(db, tenant_id, code)
    if not row or row.status not in ("enabled", "trial"):
        return False
    if row.status == "trial" and row.trial_ends_at:
        trial_end = row.trial_ends_at
        if trial_end.tzinfo is None:
            trial_end = trial_end.replace(tzinfo=timezone.utc)
        if trial_end < datetime.now(timezone.utc):
            return False
    service = db.get(Service, code)
    return bool(service and service.is_active)


def enabled_features(db: Session, tenant_id: int, codes: list[str] | tuple[str, ...]) -> dict[str, bool]:
    """Пакетная проверка сервисов для витрины: один JOIN вместо 2×N запросов.

    Семантика та же, что у `is_enabled`: сервис включён, не истёк по триалу и
    активен в реестре платформы. Используется там, где нужно сразу несколько
    флагов (главная страница `/api/site`).
    """
    wanted = list(dict.fromkeys(codes))
    result = {code: False for code in wanted}
    if not wanted:
        return result
    rows = db.execute(
        select(
            TenantService.service_code,
            TenantService.status,
            TenantService.trial_ends_at,
            Service.is_active,
        )
        .join(Service, Service.code == TenantService.service_code)
        .where(
            TenantService.tenant_id == tenant_id,
            TenantService.service_code.in_(wanted),
        )
    ).all()
    now = datetime.now(timezone.utc)
    for code, status, trial_ends_at, is_active in rows:
        if not is_active or status not in ("enabled", "trial"):
            continue
        if status == "trial" and trial_ends_at:
            if trial_ends_at.tzinfo is None:
                trial_ends_at = trial_ends_at.replace(tzinfo=timezone.utc)
            if trial_ends_at < now:
                continue
        result[code] = True
    return result
