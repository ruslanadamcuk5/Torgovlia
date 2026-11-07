"""Инциденты платформы: создание, хронология и статус-страница."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.deps import require_platform
from app.models import (
    INCIDENT_RESOLVED,
    INCIDENT_SEVERITIES,
    INCIDENT_STATUSES,
    Incident,
    IncidentUpdate,
    PlatformUser,
    Tenant,
)
from app.schemas import (
    IncidentIn,
    IncidentListOut,
    IncidentOut,
    IncidentUpdateIn,
)
from app.services.audit import audit


router = APIRouter(prefix="/platform/incidents", tags=["Платформа: инциденты"])


def _incident_or_404(db: Session, incident_id: int) -> Incident:
    incident = db.scalar(
        select(Incident)
        .where(Incident.id == incident_id)
        .options(selectinload(Incident.updates))
        .execution_options(skip_tenant_filter=True)
    )
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Инцидент не найден")
    return incident


def _payload(incident: Incident, tenant_name: str | None = None) -> IncidentOut:
    data = IncidentOut.model_validate(incident)
    return data.model_copy(update={"tenant_name": tenant_name})


@router.get("", response_model=IncidentListOut, summary="Список инцидентов")
def list_incidents(
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
    state: str = Query(default="all", pattern="^(active|resolved|all)$"),
    tenant_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=300),
):
    query = (
        select(Incident)
        .options(selectinload(Incident.updates))
        .execution_options(skip_tenant_filter=True)
    )
    if state == "active":
        query = query.where(Incident.status != INCIDENT_RESOLVED)
    elif state == "resolved":
        query = query.where(Incident.status == INCIDENT_RESOLVED)
    if tenant_id is not None:
        query = query.where(Incident.tenant_id == tenant_id)
    items = db.scalars(query.order_by(Incident.started_at.desc()).limit(limit)).all()

    tenant_ids = {item.tenant_id for item in items if item.tenant_id}
    names: dict[int, str] = {}
    if tenant_ids:
        names = {
            tenant.id: tenant.name
            for tenant in db.scalars(select(Tenant).where(Tenant.id.in_(tenant_ids))).all()
        }
    return {
        "items": [_payload(item, names.get(item.tenant_id or 0)) for item in items],
        "total": len(items),
    }


@router.post("", response_model=IncidentOut, status_code=status.HTTP_201_CREATED, summary="Открыть инцидент")
def create_incident(
    payload: IncidentIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    if payload.severity not in INCIDENT_SEVERITIES:
        raise HTTPException(status_code=422, detail="Неизвестная важность инцидента")
    tenant = None
    if payload.tenant_id is not None:
        tenant = db.get(Tenant, payload.tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Арендатор не найден")

    author = user.full_name or user.phone
    incident = Incident(
        tenant_id=tenant.id if tenant else None,
        title=payload.title.strip(),
        body=payload.body.strip(),
        severity=payload.severity,
        status="investigating",
        created_by=author,
    )
    db.add(incident)
    db.flush()
    db.add(
        IncidentUpdate(
            incident_id=incident.id,
            status=incident.status,
            body=incident.body or "Инцидент зарегистрирован, выясняем причину.",
            author=author,
        )
    )
    audit(
        db,
        "platform.incident.create",
        actor=author,
        platform_user_id=user.id,
        tenant_id=incident.tenant_id,
        entity="incident",
        entity_id=str(incident.id),
        details={"severity": incident.severity, "title": incident.title},
    )
    db.commit()
    db.refresh(incident)
    return _payload(incident, tenant.name if tenant else None)


@router.post(
    "/{incident_id}/updates",
    response_model=IncidentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить запись в хронологию инцидента",
)
def add_incident_update(
    incident_id: int,
    payload: IncidentUpdateIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    incident = _incident_or_404(db, incident_id)
    next_status = payload.status or incident.status
    if next_status not in INCIDENT_STATUSES:
        raise HTTPException(status_code=422, detail="Неизвестный статус инцидента")

    author = user.full_name or user.phone
    now = datetime.now(timezone.utc)
    db.add(
        IncidentUpdate(
            incident_id=incident.id,
            status=next_status,
            body=payload.body.strip(),
            author=author,
        )
    )
    incident.status = next_status
    incident.updated_at = now
    if next_status == INCIDENT_RESOLVED:
        incident.resolved_at = now
    else:
        incident.resolved_at = None

    tenant_name = None
    if incident.tenant_id:
        tenant = db.get(Tenant, incident.tenant_id)
        tenant_name = tenant.name if tenant else None

    audit(
        db,
        "platform.incident.update",
        actor=author,
        platform_user_id=user.id,
        tenant_id=incident.tenant_id,
        entity="incident",
        entity_id=str(incident.id),
        details={"status": next_status, "body": payload.body.strip()[:200]},
    )
    db.commit()
    db.refresh(incident)
    return _payload(incident, tenant_name)
