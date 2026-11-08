"""API сервисов в админке арендатора."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import Tenant, User
from app.platform.entitlements import disable, enable, list_for_tenant
from app.platform.service_details import detail_for
from app.schemas import ServiceDetailOut, ServiceListOut, ServiceOut
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


@router.get("/{code}", response_model=ServiceDetailOut, summary="Подробно о сервисе")
def service_detail(
    code: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tenant = _tenant(db)
    items, _plan = list_for_tenant(db, tenant)
    item = next((entry for entry in items if entry["code"] == code), None)
    if not item:
        raise HTTPException(status_code=404, detail="Сервис не найден")

    detail = detail_for(code)
    by_code = {entry["code"]: entry for entry in items}

    def link(entry: dict) -> dict:
        return {
            "code": entry["code"],
            "title": entry["title"],
            "group": entry["group"],
            "description": entry["description"],
            "enabled": entry["enabled"],
            "readiness": entry["readiness"],
            "readiness_title": entry["readiness_title"],
            "readiness_note": entry["readiness_note"],
        }

    related = [
        link(entry)
        for entry in items
        if entry["group"] == item["group"] and entry["code"] != code
    ][:6]
    dependency_services = [link(by_code[dep]) for dep in item["dependencies"] if dep in by_code]

    return {
        **item,
        "about": detail.get("about") or item["description"],
        "audience": detail.get("audience") or "",
        "features": list(detail.get("features") or []),
        "related": related,
        "dependency_services": dependency_services,
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
