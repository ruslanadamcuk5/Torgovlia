"""Публичная статус-страница платформы."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import INCIDENT_CRITICAL, INCIDENT_RESOLVED, Incident
from app.platform import settings as platform_settings
from app.schemas import StatusIncidentOut, StatusPageOut


router = APIRouter(prefix="/status", tags=["Статус платформы"])


def _public_incident(incident: Incident) -> StatusIncidentOut:
    return StatusIncidentOut.model_validate(incident)


@router.get("", response_model=StatusPageOut, summary="Состояние платформы и история инцидентов")
def status_page(db: Session = Depends(get_db)):
    active = db.scalars(
        select(Incident)
        .where(Incident.status != INCIDENT_RESOLVED)
        .options(selectinload(Incident.updates))
        .order_by(Incident.started_at.desc())
        .execution_options(skip_tenant_filter=True)
    ).all()
    since = datetime.now(timezone.utc) - timedelta(days=14)
    resolved = db.scalars(
        select(Incident)
        .where(Incident.status == INCIDENT_RESOLVED, Incident.resolved_at >= since)
        .options(selectinload(Incident.updates))
        .order_by(Incident.resolved_at.desc())
        .limit(20)
        .execution_options(skip_tenant_filter=True)
    ).all()

    if any(item.severity == INCIDENT_CRITICAL for item in active):
        overall = "outage"
    elif active:
        overall = "degraded"
    else:
        overall = "operational"

    config = platform_settings.get_config(db)
    return {
        "updated_at": datetime.now(timezone.utc),
        "brand_name": config.get("brand_name") or "Torgovlia",
        "maintenance_notice": config.get("maintenance_notice") or "",
        "active": [_public_incident(item) for item in active],
        "resolved": [_public_incident(item) for item in resolved],
        "overall": overall,
    }
