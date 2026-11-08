"""Публичная телеметрия интереса к платформе и отчёты для панели."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import client_ip, require_platform
from app.models import PlatformUser, Tenant
from app.platform import analytics, demo
from app.schemas import PlatformTrackIn


router = APIRouter(prefix="/platform", tags=["Платформа: аналитика интереса"])

_WINDOW = 3600
_MAX = 240
_seen: dict[str, list[float]] = {}


def _allowed(ip: str) -> bool:
    now = time.monotonic()
    stamps = [stamp for stamp in _seen.get(ip, []) if now - stamp < _WINDOW]
    if len(stamps) >= _MAX:
        _seen[ip] = stamps
        return False
    stamps.append(now)
    _seen[ip] = stamps
    return True


@router.post("/track", status_code=204, summary="Событие интереса к платформе")
def track(
    payload: PlatformTrackIn,
    request: Request,
    db: Session = Depends(get_db),
):
    ip = client_ip(request)
    if not _allowed(ip or "unknown"):
        return Response(status_code=204)
    analytics.remember(
        db,
        kind=payload.kind,
        path=payload.path,
        referrer=payload.referrer or request.headers.get("referer", ""),
        source=payload.source,
        campaign=payload.campaign,
        session_key=payload.session_key,
        ip=ip,
        user_agent=request.headers.get("user-agent", ""),
        detail=payload.detail,
    )
    db.commit()
    return Response(status_code=204)


@router.get("/analytics", summary="Интерес к платформе: визиты, демо и регистрации")
def analytics_report(
    days: int = Query(default=30, ge=1, le=365),
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    return analytics.overview(db, days)


@router.get("/demo", summary="Параметры демо-магазина")
def demo_info(db: Session = Depends(get_db)):
    demo.maybe_reset(db)
    tenant = demo.demo_tenant(db)
    base = (settings.public_base_url or "").rstrip("/")
    path = f"/shop/{settings.demo_tenant_slug}"
    reset_at = demo.last_reset(db, tenant) if tenant else None
    return {
        "enabled": bool(tenant),
        "slug": settings.demo_tenant_slug,
        "name": tenant.name if tenant else "Демо-магазин",
        "storefront_url": f"{base}{path}/",
        "admin_url": f"{base}{path}/admin",
        "login_url": f"{base}{path}/login",
        "phone": settings.demo_admin_phone,
        "password": settings.demo_admin_password,
        "reset_every_hours": settings.demo_reset_hours,
        "reset_at": reset_at,
    }


@router.post("/demo/reset", summary="Сбросить демо-магазин вручную")
def demo_reset(
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenant = demo.demo_tenant(db)
    if tenant is None:
        return {"ok": False, "reason": "Демо-магазин не найден"}
    result = demo.reset(db, tenant)
    return {"ok": True, **result}
