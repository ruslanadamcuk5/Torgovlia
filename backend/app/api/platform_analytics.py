"""Публичная телеметрия интереса к платформе и отчёты для панели."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
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
    service_slug = settings.service_demo_tenant_slug
    service_tenant = (
        db.scalar(select(Tenant).where(Tenant.slug == service_slug))
        if service_slug
        else None
    )
    service_path = f"/shop/{service_slug}"
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
        "service_demo": (
            {
                "enabled": True,
                "slug": service_slug,
                "name": service_tenant.name,
                "storefront_url": f"{base}{service_path}/",
                "admin_url": f"{base}{service_path}/admin",
                "booking_url": f"{base}{service_path}/booking",
                "phone": service_tenant.phone if getattr(service_tenant, "phone", "") else "",
            }
            if service_tenant
            else {"enabled": False}
        ),
    }


@router.post("/demo/reset", summary="Сбросить демо вручную")
def demo_reset(
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenants = demo.demo_tenants(db)
    if not tenants:
        return {"ok": False, "reason": "Демо-магазин не найден"}
    results = [demo.reset(db, tenant) for tenant in tenants]
    main = next(
        (item for item in results if item["slug"] == settings.demo_tenant_slug),
        results[0],
    )
    return {"ok": True, **main, "tenants": results}
