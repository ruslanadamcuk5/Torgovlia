"""Проверка и изменение прав на сервисы (entitlements)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Service, Tenant, TenantService
from app.platform.catalog import (
    SERVICE_BY_CODE,
    SERVICE_CATALOG,
    TIER_ADDON,
    TIER_PLATFORM,
    included_in_plan,
)
from app.platform.sync import (
    _service_row,
    _subscription,
    ensure_tenant_services,
    is_enabled,
    plan_for_tenant,
)


def _error(code: str, message: str, http_status: int = status.HTTP_409_CONFLICT, **extra):
    detail = {"code": code, "message": message, **extra}
    raise HTTPException(status_code=http_status, detail=detail)


def _trial_active(row: TenantService | None) -> bool:
    if not row or row.status != "trial" or not row.trial_ends_at:
        return False
    trial_end = row.trial_ends_at
    if trial_end.tzinfo is None:
        trial_end = trial_end.replace(tzinfo=timezone.utc)
    return trial_end >= datetime.now(timezone.utc)


def _payload(
    service: Service,
    row: TenantService | None,
    plan_code: str,
    enabled_codes: set[str],
) -> dict:
    included = included_in_plan(service.code, plan_code)
    current = row.status if row else ("enabled" if included and service.default_enabled else "disabled")
    trial = _trial_active(row)
    if trial:
        current = "trial"
    locked = bool(row and row.locked_by_platform)
    enabled = current in ("enabled", "trial")

    dependencies_enabled = all(dep in enabled_codes for dep in service.dependencies)
    can_enable = (
        not enabled
        and not locked
        and service.tier != TIER_PLATFORM
        and (included or service.tier == TIER_ADDON)
        and dependencies_enabled
    )
    can_disable = enabled and not locked and not any(
        service.code in item.dependencies and item.code in enabled_codes
        for item in SERVICE_CATALOG
    )

    if included:
        reason = "included"
    elif service.tier == TIER_ADDON:
        reason = "payment_required" if service.price_month and service.price_month > 0 else "available"
    elif service.tier == TIER_PLATFORM:
        reason = "platform_only"
    else:
        reason = "upgrade_plan"

    if locked:
        reason = "locked_by_platform"
    elif not dependencies_enabled:
        reason = "dependencies_required"

    return {
        "code": service.code,
        "title": service.title,
        "group": service.group,
        "description": service.description,
        "tier": service.tier,
        "price_month": float(service.price_month or 0),
        "status": current,
        "enabled": enabled,
        "included_in_plan": included,
        "can_enable": can_enable,
        "can_disable": can_disable,
        "reason": reason,
        "dependencies": list(service.dependencies or []),
        "trial_days": int(service.trial_days or 0),
        "locked_by_platform": locked,
        "icon": service.icon,
    }


def _enabled_codes(db: Session, tenant_id: int) -> set[str]:
    return {item.code for item in SERVICE_CATALOG if is_enabled(db, tenant_id, item.code)}


def list_for_tenant(db: Session, tenant: Tenant) -> tuple[list[dict], str]:
    ensure_tenant_services(db, tenant)
    plan_code = plan_for_tenant(db, tenant.id)
    rows = {
        row.service_code: row
        for row in db.scalars(
            select(TenantService)
            .where(TenantService.tenant_id == tenant.id)
            .execution_options(skip_tenant_filter=True)
        ).all()
    }
    services = db.scalars(
        select(Service).where(Service.is_active.is_(True)).order_by(Service.group, Service.sort_order)
    ).all()
    enabled_codes = _enabled_codes(db, tenant.id)
    return [_payload(service, rows.get(service.code), plan_code, enabled_codes) for service in services], plan_code


def enable(db: Session, tenant: Tenant, code: str) -> dict:
    definition = SERVICE_BY_CODE.get(code)
    service = db.get(Service, code)
    if not definition or not service or not service.is_active:
        _error("unknown_service", "Сервис не найден", status.HTTP_404_NOT_FOUND)

    ensure_tenant_services(db, tenant)
    row = _service_row(db, tenant.id, code)
    if not row:
        _error("unknown_service", "Сервис не найден для этого магазина", status.HTTP_404_NOT_FOUND)
    if row.locked_by_platform:
        _error("locked_by_platform", "Сервис заблокирован платформой. Обратитесь в поддержку.")

    enabled_codes = _enabled_codes(db, tenant.id)
    if code in enabled_codes:
        return _payload(service, row, plan_for_tenant(db, tenant.id), enabled_codes)
    missing = [dep for dep in definition.dependencies if dep not in enabled_codes]
    if missing:
        _error(
            "dependencies_required",
            "Сначала включите зависимые сервисы",
            missing=missing,
        )

    plan_code = plan_for_tenant(db, tenant.id)
    included = included_in_plan(code, plan_code)
    if not included:
        if definition.tier == TIER_PLATFORM:
            _error(
                "platform_only",
                "Этот сервис подключает только платформа",
                status.HTTP_403_FORBIDDEN,
            )
        if definition.tier != TIER_ADDON:
            _error(
                "upgrade_plan",
                "Сервис недоступен на текущем тарифе",
                status.HTTP_403_FORBIDDEN,
                plan=plan_code,
            )
        if service.price_month and service.price_month > 0:
            row.status = "pending_payment"
            row.source = "addon"
            db.commit()
            _error(
                "payment_required",
                "Для подключения нужна оплата",
                status.HTTP_402_PAYMENT_REQUIRED,
                price_month=float(service.price_month),
            )

    now = datetime.now(timezone.utc)
    row.status = "enabled"
    row.source = "plan" if included else "addon"
    row.enabled_at = row.enabled_at or now
    row.disabled_at = None
    db.commit()
    db.refresh(row)
    enabled_codes.add(code)
    return _payload(service, row, plan_code, enabled_codes)


def disable(db: Session, tenant: Tenant, code: str) -> dict:
    service = db.get(Service, code)
    if not service:
        _error("unknown_service", "Сервис не найден", status.HTTP_404_NOT_FOUND)
    ensure_tenant_services(db, tenant)
    row = _service_row(db, tenant.id, code)
    if not row:
        _error("unknown_service", "Сервис не найден для этого магазина", status.HTTP_404_NOT_FOUND)
    if row.locked_by_platform:
        _error("locked_by_platform", "Сервис заблокирован платформой")

    dependents = [
        item.code
        for item in SERVICE_CATALOG
        if code in item.dependencies and is_enabled(db, tenant.id, item.code)
    ]
    if dependents:
        _error(
            "dependencies_active",
            "Сначала отключите сервисы, которые зависят от этого",
            dependents=dependents,
        )

    row.status = "disabled"
    row.disabled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    enabled_codes = _enabled_codes(db, tenant.id)
    return _payload(service, row, plan_for_tenant(db, tenant.id), enabled_codes)


def platform_update(
    db: Session,
    tenant: Tenant,
    code: str,
    *,
    status_value: str | None = None,
    locked_by_platform: bool | None = None,
    config: dict | None = None,
) -> dict:
    service = db.get(Service, code)
    if not service:
        _error("unknown_service", "Сервис не найден", status.HTTP_404_NOT_FOUND)
    ensure_tenant_services(db, tenant)
    row = _service_row(db, tenant.id, code)
    if not row:
        _error("unknown_service", "Сервис не найден для этого магазина", status.HTTP_404_NOT_FOUND)

    if status_value is not None:
        if status_value not in ("enabled", "disabled", "trial", "pending_payment", "suspended"):
            _error("invalid_status", "Недопустимый статус сервиса", status.HTTP_422_UNPROCESSABLE_ENTITY)
        row.status = status_value
        if status_value in ("enabled", "trial"):
            row.enabled_at = row.enabled_at or datetime.now(timezone.utc)
            row.disabled_at = None
        else:
            row.disabled_at = datetime.now(timezone.utc)
    if locked_by_platform is not None:
        row.locked_by_platform = locked_by_platform
    if config is not None:
        row.config = config
    db.commit()
    db.refresh(row)
    enabled_codes = _enabled_codes(db, tenant.id)
    return _payload(service, row, plan_for_tenant(db, tenant.id), enabled_codes)
