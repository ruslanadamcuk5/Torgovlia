"""API сервисов в админке арендатора."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import Tenant, User
from app.platform.entitlements import disable, enable, list_for_tenant
from app.schemas import ServiceListOut, ServiceOut
from app.tenancy import current_tenant
from app.services.audit import audit


router = APIRouter(prefix="/admin/services", tags=["Сервисы магазина"])


def _tenant(db: Session) -> Tenant:
    context = current_tenant()
    tenant = db.get(Tenant, context.id) if context else None
    if not tenant:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    return tenant


@router.get("", response_model=ServiceListOut, summary="Сервисы магазина")
def services(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    tenant = _tenant(db)
    items, plan_code = list_for_tenant(db, tenant)
    return {"plan_code": plan_code, "items": items}


@router.get("/features", summary="Включённые сервисы для интерфейса")
def features(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    tenant = _tenant(db)
    items, _plan = list_for_tenant(db, tenant)
    return {
        "services": {item["code"]: item["enabled"] for item in items},
        "plan": _plan,
    }


@router.post("/{code}/enable", response_model=ServiceOut, summary="Включить сервис")
def enable_service(
    code: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tenant = _tenant(db)
    result = enable(db, tenant, code)
    audit(
        db,
        "service.enable",
        actor=user.full_name or user.phone,
        user_id=user.id,
        tenant_id=tenant.id,
        entity="service",
        entity_id=code,
    )
    db.commit()
    return result


@router.post("/{code}/disable", response_model=ServiceOut, summary="Отключить сервис")
def disable_service(
    code: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tenant = _tenant(db)
    result = disable(db, tenant, code)
    audit(
        db,
        "service.disable",
        actor=user.full_name or user.phone,
        user_id=user.id,
        tenant_id=tenant.id,
        entity="service",
        entity_id=code,
    )
    db.commit()
    return result
