"""Проверки доступности витрин: статус, код ответа и задержка.

Модуль не зависит от планировщика: проверки запускаются кнопкой в панели или
внешним cron через API. История хранится в `uptime_checks`, поэтому панель
показывает доступность и задержку за окно без повторных запросов к сайтам.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.models import (
    TENANT_ARCHIVED,
    Tenant,
    UptimeCheck,
    utcnow,
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def probe_url(tenant: Tenant) -> str:
    """Адрес проверки: свой домен, адрес публикации или демо-витрина."""
    deploy_url = (tenant.deploy_url or "").strip()
    if deploy_url.startswith(("http://", "https://")):
        return deploy_url.rstrip("/") + "/api/site"

    if app_settings.demo_mode and app_settings.public_base_url:
        base = app_settings.public_base_url.rstrip("/")
        return f"{base}/api/site"

    domain = next((item for item in tenant.domains if item.is_primary), None)
    if domain is None and tenant.domains:
        domain = tenant.domains[0]
    if domain is None:
        return ""
    return f"https://{domain.host}/api/site"


def _ssl_context() -> ssl.SSLContext:
    # Демо-стенды часто с самоподписанным или ещё не выпущенным сертификатом;
    # доступность важнее строгой проверки цепочки, SSL-статус ведётся отдельно.
    return ssl._create_unverified_context()  # noqa: SLF001


def probe_tenant(tenant: Tenant, timeout: float = 8.0) -> UptimeCheck | None:
    url = probe_url(tenant)
    if not url:
        return None

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "torgovlia-uptime/1.0",
            "X-Tenant-Slug": tenant.slug,
        },
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=_ssl_context()),
    )
    started = time.perf_counter()
    status_code: int | None = None
    error = ""
    ok = False
    try:
        with opener.open(request, timeout=timeout) as response:
            status_code = response.status
            body = response.read(200_000)
            ok = status_code == 200 and _looks_like_site(body, tenant.slug)
            if not ok and status_code == 200:
                error = "Ответ не похож на витрину магазина"
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        error = f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        error = str(exc)[:280]
    latency_ms = int((time.perf_counter() - started) * 1000)

    return UptimeCheck(
        tenant_id=tenant.id,
        url=url,
        ok=ok,
        status_code=status_code,
        latency_ms=latency_ms,
        error=error,
        checked_at=now(),
    )


def _looks_like_site(body: bytes, slug: str) -> bool:
    try:
        payload = json.loads(body.decode("utf-8", "replace"))
    except (ValueError, UnicodeError):
        return False
    tenant = payload.get("tenant") if isinstance(payload, dict) else None
    return isinstance(tenant, dict) and tenant.get("slug") == slug


def run_checks(db: Session, tenants: list[Tenant] | None = None) -> dict:
    if tenants is None:
        tenants = list(
            db.scalars(
                select(Tenant)
                .where(Tenant.status != TENANT_ARCHIVED)
                .order_by(Tenant.id)
                .execution_options(skip_tenant_filter=True)
            ).all()
        )
    checks: list[UptimeCheck] = []
    for tenant in tenants:
        if tenant.status == TENANT_ARCHIVED:
            continue
        check = probe_tenant(tenant)
        if check is None:
            continue
        db.add(check)
        checks.append(check)
    db.commit()
    for check in checks:
        db.refresh(check)
    return {
        "checked": len(checks),
        "ok": sum(1 for item in checks if item.ok),
        "failed": sum(1 for item in checks if not item.ok),
        "results": checks,
    }


def _percentile(values: list[int], share: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(share * (len(ordered) - 1))))
    return ordered[index]


def summarize(checks: list[UptimeCheck]) -> dict:
    if not checks:
        return {
            "checks": 0,
            "uptime_24h": None,
            "avg_latency_ms": None,
            "p95_latency_ms": None,
            "last_ok": None,
            "last_status_code": None,
            "last_latency_ms": None,
            "last_checked_at": None,
        }
    ordered = sorted(checks, key=lambda item: item.checked_at)
    last = ordered[-1]
    ok_count = sum(1 for item in checks if item.ok)
    latencies = [item.latency_ms for item in checks if item.ok]
    return {
        "checks": len(checks),
        "uptime_24h": round(100 * ok_count / len(checks), 1),
        "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
        "p95_latency_ms": _percentile(latencies, 0.95),
        "last_ok": last.ok,
        "last_status_code": last.status_code,
        "last_latency_ms": last.latency_ms,
        "last_checked_at": last.checked_at,
    }


def summary(db: Session, tenant_id: int, hours: int = 24) -> dict:
    cutoff = now() - timedelta(hours=max(1, min(hours, 24 * 30)))
    rows = list(
        db.scalars(
            select(UptimeCheck)
            .where(
                UptimeCheck.tenant_id == tenant_id,
                UptimeCheck.checked_at >= cutoff,
            )
            .order_by(UptimeCheck.checked_at)
            .execution_options(skip_tenant_filter=True)
        ).all()
    )
    return summarize(rows)


def summaries(db: Session, tenant_ids: list[int], hours: int = 24) -> dict[int, dict]:
    if not tenant_ids:
        return {}
    cutoff = now() - timedelta(hours=max(1, min(hours, 24 * 30)))
    rows = db.scalars(
        select(UptimeCheck)
        .where(
            UptimeCheck.tenant_id.in_(tenant_ids),
            UptimeCheck.checked_at >= cutoff,
        )
        .order_by(UptimeCheck.checked_at)
        .execution_options(skip_tenant_filter=True)
    ).all()
    grouped: dict[int, list[UptimeCheck]] = {tenant_id: [] for tenant_id in tenant_ids}
    for row in rows:
        grouped.setdefault(row.tenant_id, []).append(row)
    return {tenant_id: summarize(items) for tenant_id, items in grouped.items()}
