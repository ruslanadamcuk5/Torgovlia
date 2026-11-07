"""Жизненный цикл магазина: приостановка, возобновление, архив, восстановление.

Все действия выполняются только из панели платформы, требуют причины и
записываются в аудит. Приостановка не удаляет данные: витрина и админка
перестают обслуживаться, а сайт можно вернуть одним действием.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    TENANT_ACTIVE,
    TENANT_ARCHIVED,
    TENANT_GRACE,
    TENANT_ONBOARDING,
    TENANT_SUSPENDED,
    Tenant,
    utcnow,
)
from app.platform.ops import DEPLOY_PAUSED, hosting_payload
from app.services.audit import audit


ACTION_SUSPEND = "suspend"
ACTION_RESUME = "resume"
ACTION_ARCHIVE = "archive"
ACTION_RESTORE = "restore"
ACTIONS = (ACTION_SUSPEND, ACTION_RESUME, ACTION_ARCHIVE, ACTION_RESTORE)

ACTION_LABEL = {
    ACTION_SUSPEND: "Приостановлен",
    ACTION_RESUME: "Возобновлён",
    ACTION_ARCHIVE: "Архивирован",
    ACTION_RESTORE: "Восстановлен",
}

# Какие исходные статусы допустимы для каждого действия.
_ALLOWED = {
    ACTION_SUSPEND: (TENANT_ACTIVE, TENANT_GRACE, TENANT_ONBOARDING),
    ACTION_RESUME: (TENANT_SUSPENDED,),
    ACTION_ARCHIVE: (
        TENANT_ACTIVE,
        TENANT_GRACE,
        TENANT_ONBOARDING,
        TENANT_SUSPENDED,
    ),
    ACTION_RESTORE: (TENANT_ARCHIVED,),
}


def _error(code: str, message: str, http_status: int = status.HTTP_409_CONFLICT) -> None:
    raise HTTPException(
        status_code=http_status,
        detail={"code": code, "message": message},
    )


def apply_action(
    db: Session,
    tenant: Tenant,
    action: str,
    *,
    reason: str,
    actor: str = "",
    platform_user_id: int | None = None,
) -> Tenant:
    if action not in ACTIONS:
        _error("unknown_action", "Неизвестное действие", status.HTTP_422_UNPROCESSABLE_ENTITY)
    reason = (reason or "").strip()
    if len(reason) < 3:
        _error("reason_required", "Укажите причину действия")

    allowed = _ALLOWED[action]
    if tenant.status not in allowed:
        _error(
            "invalid_transition",
            f"Действие «{ACTION_LABEL[action]}» недоступно в статусе «{tenant.status}»",
        )

    previous = tenant.status
    if action == ACTION_SUSPEND:
        tenant.status = TENANT_SUSPENDED
        if tenant.deploy_status == "deployed":
            tenant.deploy_status = DEPLOY_PAUSED
    elif action == ACTION_RESUME:
        tenant.status = TENANT_ACTIVE
        if tenant.deploy_status == DEPLOY_PAUSED:
            tenant.deploy_status = "deployed"
    elif action == ACTION_ARCHIVE:
        tenant.status = TENANT_ARCHIVED
    elif action == ACTION_RESTORE:
        # Восстанавливаем в настройку: владелец проходит проверку и оплату заново.
        tenant.status = TENANT_ONBOARDING

    tenant.updated_at = utcnow()
    audit(
        db,
        f"tenant.lifecycle.{action}",
        actor=actor,
        platform_user_id=platform_user_id,
        tenant_id=tenant.id,
        entity="tenant",
        entity_id=str(tenant.id),
        details={"from": previous, "to": tenant.status, "reason": reason},
    )
    db.commit()
    db.refresh(tenant)
    return tenant


def lifecycle_payload(tenant: Tenant) -> dict:
    actions = []
    for action in ACTIONS:
        actions.append(
            {
                "action": action,
                "label": {
                    ACTION_SUSPEND: "Приостановить",
                    ACTION_RESUME: "Возобновить",
                    ACTION_ARCHIVE: "Архивировать",
                    ACTION_RESTORE: "Восстановить",
                }[action],
                "enabled": tenant.status in _ALLOWED[action],
            }
        )
    return {
        "tenant_id": tenant.id,
        "status": tenant.status,
        "actions": actions,
        "hosting": hosting_payload(tenant),
    }
