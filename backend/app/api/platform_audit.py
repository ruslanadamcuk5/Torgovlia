"""Журнал действий платформы: поиск, фильтры и выгрузка в CSV."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_platform
from app.models import AuditLog, PlatformUser, Tenant
from app.schemas import AuditListOut


router = APIRouter(prefix="/platform/audit", tags=["Платформа: журнал действий"])

MAX_EXPORT_ROWS = 5000


def _filters(
    tenant_id: int | None,
    actor: str | None,
    action: str | None,
    query: str | None,
    date_from: date | None,
    date_to: date | None,
) -> list:
    conditions = []
    if tenant_id is not None:
        conditions.append(AuditLog.tenant_id == tenant_id)
    if actor:
        conditions.append(AuditLog.actor.ilike(f"%{actor.strip()}%"))
    if action:
        conditions.append(AuditLog.action == action.strip())
    if query:
        needle = f"%{query.strip()}%"
        conditions.append(
            or_(
                AuditLog.actor.ilike(needle),
                AuditLog.action.ilike(needle),
                AuditLog.entity.ilike(needle),
                AuditLog.entity_id.ilike(needle),
            )
        )
    if date_from:
        start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        conditions.append(AuditLog.created_at >= start)
    if date_to:
        end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        conditions.append(AuditLog.created_at < end)
    return conditions


@router.get("", response_model=AuditListOut, summary="Журнал действий с фильтрами")
def list_audit(
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
    tenant_id: int | None = Query(default=None, ge=1),
    actor: str | None = Query(default=None, max_length=120),
    action: str | None = Query(default=None, max_length=80),
    q: str | None = Query(default=None, max_length=120),
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    conditions = _filters(tenant_id, actor, action, q, date_from, date_to)
    total = db.scalar(select(func.count()).select_from(AuditLog).where(*conditions)) or 0
    items = db.scalars(
        select(AuditLog)
        .where(*conditions)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/export", summary="Выгрузить журнал в CSV")
def export_audit(
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
    tenant_id: int | None = Query(default=None, ge=1),
    actor: str | None = Query(default=None, max_length=120),
    action: str | None = Query(default=None, max_length=80),
    q: str | None = Query(default=None, max_length=120),
    date_from: date | None = None,
    date_to: date | None = None,
):
    conditions = _filters(tenant_id, actor, action, q, date_from, date_to)
    rows = db.execute(
        select(AuditLog, Tenant.slug)
        .outerjoin(Tenant, Tenant.id == AuditLog.tenant_id)
        .where(*conditions)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(MAX_EXPORT_ROWS)
    ).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(
        [
            "id",
            "created_at_utc",
            "tenant",
            "actor",
            "action",
            "entity",
            "entity_id",
            "details",
        ]
    )
    for entry, tenant_slug in rows:
        writer.writerow(
            [
                entry.id,
                entry.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                tenant_slug or "",
                entry.actor,
                entry.action,
                entry.entity,
                entry.entity_id or "",
                ", ".join(f"{key}={value}" for key, value in (entry.details or {}).items()),
            ]
        )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="torgovlia-audit-{stamp}.csv"'},
    )
