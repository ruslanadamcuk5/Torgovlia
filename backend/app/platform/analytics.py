"""Аналитика интереса к платформе: визиты, демо и регистрации.

События обезличены: храним ключ сессии браузера, хеш IP и источник перехода.
Этого достаточно, чтобы видеть спрос, но не персональные данные.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import PlatformEvent, Tenant


VISIT = "visit"
DEMO_STOREFRONT = "demo_storefront"
DEMO_SERVICE = "demo_service"
DEMO_ADMIN = "demo_admin"
SIGNUP_START = "signup_start"
SIGNUP_CREATED = "signup_created"
PLATFORM_LOGIN = "platform_login"

KINDS = (VISIT, DEMO_STOREFRONT, DEMO_SERVICE, DEMO_ADMIN, SIGNUP_START, SIGNUP_CREATED, PLATFORM_LOGIN)

KIND_TITLES = {
    VISIT: "Визит на сайт платформы",
    DEMO_STOREFRONT: "Открыл демо-магазин",
    DEMO_SERVICE: "Открыл демо-салон",
    DEMO_ADMIN: "Открыл админку демо",
    SIGNUP_START: "Начал регистрацию",
    SIGNUP_CREATED: "Создал магазин",
    PLATFORM_LOGIN: "Вход в панель платформы",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_ip(ip: str) -> str:
    if not ip:
        return ""
    salt = settings.secret_key or "torgovlia"
    return hashlib.sha256(f"{salt}:{ip}".encode("utf-8")).hexdigest()[:32]


def remember(
    db: Session,
    *,
    kind: str,
    path: str = "",
    referrer: str = "",
    source: str = "",
    campaign: str = "",
    session_key: str = "",
    ip: str = "",
    user_agent: str = "",
    detail: str = "",
) -> PlatformEvent:
    referrer = (referrer or "").strip()[:300]
    if not source and referrer:
        host = urlparse(referrer).netloc.lower()
        source = host[4:] if host.startswith("www.") else host
        source = source[:120]
    event = PlatformEvent(
        kind=kind if kind in KINDS else VISIT,
        path=(path or "").split("?")[0][:200],
        referrer=referrer,
        source=(source or "прямой вход")[:120],
        campaign=(campaign or "")[:120],
        session_key=(session_key or "")[:64],
        ip_hash=hash_ip(ip),
        user_agent=(user_agent or "")[:300],
        detail=(detail or "")[:300],
    )
    db.add(event)
    db.flush()
    return event


def _count(db: Session, since: datetime, kind: str | None = None) -> int:
    stmt = select(func.count(PlatformEvent.id)).where(PlatformEvent.created_at >= since)
    if kind:
        stmt = stmt.where(PlatformEvent.kind == kind)
    return db.scalar(stmt) or 0


def _unique(db: Session, since: datetime, kind: str | None = None) -> int:
    stmt = select(func.count(func.distinct(PlatformEvent.session_key))).where(
        PlatformEvent.created_at >= since,
        PlatformEvent.session_key != "",
    )
    if kind:
        stmt = stmt.where(PlatformEvent.kind == kind)
    return db.scalar(stmt) or 0


def _percents(part: int, whole: int) -> float:
    if not whole:
        return 0.0
    return round(part * 100 / whole, 1)


def overview(db: Session, days: int = 30) -> dict:
    days = max(1, min(days, 365))
    since = _now() - timedelta(days=days)
    day_start = _now() - timedelta(hours=24)

    visits = _count(db, since, VISIT)
    visitors = _unique(db, since, VISIT)
    demos = _count(db, since, DEMO_STOREFRONT)
    demo_sessions = _unique(db, since, DEMO_STOREFRONT)
    admins = _count(db, since, DEMO_ADMIN)
    admin_sessions = _unique(db, since, DEMO_ADMIN)
    starts = _count(db, since, SIGNUP_START)
    created = _count(db, since, SIGNUP_CREATED)
    logins = _count(db, since, PLATFORM_LOGIN)

    today = _now().date()
    daily: list[dict] = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        rows = db.execute(
            select(PlatformEvent.kind, func.count(PlatformEvent.id))
            .where(PlatformEvent.created_at >= start, PlatformEvent.created_at < end)
            .group_by(PlatformEvent.kind)
        ).all()
        counts = {kind: count for kind, count in rows}
        sessions = db.scalar(
            select(func.count(func.distinct(PlatformEvent.session_key))).where(
                PlatformEvent.created_at >= start,
                PlatformEvent.created_at < end,
                PlatformEvent.kind == VISIT,
                PlatformEvent.session_key != "",
            )
        ) or 0
        daily.append(
            {
                "date": day.isoformat(),
                "visits": counts.get(VISIT, 0),
                "visitors": sessions,
                "demos": counts.get(DEMO_STOREFRONT, 0),
                "admins": counts.get(DEMO_ADMIN, 0),
                "signups": counts.get(SIGNUP_START, 0),
                "created": counts.get(SIGNUP_CREATED, 0),
            }
        )

    sources = db.execute(
        select(PlatformEvent.source, func.count(PlatformEvent.id))
        .where(PlatformEvent.created_at >= since, PlatformEvent.kind == VISIT)
        .group_by(PlatformEvent.source)
        .order_by(func.count(PlatformEvent.id).desc())
        .limit(8)
    ).all()

    pages = db.execute(
        select(PlatformEvent.path, func.count(PlatformEvent.id))
        .where(PlatformEvent.created_at >= since, PlatformEvent.kind == VISIT)
        .group_by(PlatformEvent.path)
        .order_by(func.count(PlatformEvent.id).desc())
        .limit(6)
    ).all()

    recent = db.scalars(
        select(PlatformEvent).order_by(PlatformEvent.id.desc()).limit(25)
    ).all()

    online = db.scalar(
        select(func.count(func.distinct(PlatformEvent.session_key))).where(
            PlatformEvent.created_at >= _now() - timedelta(minutes=30),
            PlatformEvent.session_key != "",
        )
    ) or 0

    tenants = db.scalars(
        select(Tenant).where(Tenant.created_at >= since).order_by(Tenant.created_at.desc()).limit(8)
    ).all()

    return {
        "days": days,
        "generated_at": _now(),
        "summary": {
            "visits": visits,
            "visitors": visitors,
            "demos": demos,
            "demo_sessions": demo_sessions,
            "admins": admins,
            "admin_sessions": admin_sessions,
            "signup_starts": starts,
            "signup_created": created,
            "platform_logins": logins,
            "online_30m": online,
            "visits_24h": _count(db, day_start, VISIT),
            "demo_24h": _count(db, day_start, DEMO_STOREFRONT),
            "signups_24h": _count(db, day_start, SIGNUP_START),
            "visit_to_demo": _percents(demo_sessions, visitors),
            "demo_to_admin": _percents(admin_sessions, demo_sessions),
            "visit_to_signup": _percents(starts, visitors),
            "signup_to_created": _percents(created, starts),
        },
        "funnel": [
            {"code": VISIT, "title": "Визиты на сайт", "value": visitors},
            {"code": DEMO_STOREFRONT, "title": "Открыли демо", "value": demo_sessions},
            {"code": DEMO_ADMIN, "title": "Зашли в админку демо", "value": admin_sessions},
            {"code": SIGNUP_START, "title": "Начали регистрацию", "value": starts},
            {"code": SIGNUP_CREATED, "title": "Создали магазин", "value": created},
        ],
        "daily": daily,
        "sources": [{"source": source or "прямой вход", "count": count} for source, count in sources],
        "pages": [{"path": path or "/", "count": count} for path, count in pages],
        "recent": [
            {
                "id": event.id,
                "kind": event.kind,
                "title": KIND_TITLES.get(event.kind, event.kind),
                "path": event.path,
                "source": event.source,
                "detail": event.detail,
                "created_at": event.created_at,
            }
            for event in recent
        ],
        "tenants": [
            {
                "id": tenant.id,
                "name": tenant.name,
                "slug": tenant.slug,
                "created_at": tenant.created_at,
            }
            for tenant in tenants
        ],
    }
