"""Хостинг, публикация и мониторинг запусков.

Провайдер hoster.by не даёт публичного API заказа услуг, поэтому запуск идёт в
ручном/ассистируемом режиме: платформа ведёт очередь задач и чек-лист, сотрудник
выполняет шаги в панели провайдера и отмечает результат. Модель задачи и шагов
позволяет позже подключить автоматический адаптер, не меняя интерфейсы.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    DEPLOY_DEPLOYED,
    DEPLOY_FAILED,
    DEPLOY_IN_PROGRESS,
    DEPLOY_NOT_STARTED,
    DEPLOY_PAUSED,
    DEPLOY_QUEUED,
    DEPLOY_STATUSES,
    TENANT_ACTIVE,
    TENANT_ONBOARDING,
    Invoice,
    ProvisioningJob,
    Tenant,
    TenantDomain,
    utcnow,
)
from app.platform import uptime


JOB_QUEUED = "queued"
JOB_IN_PROGRESS = "in_progress"
JOB_DONE = "done"
JOB_BLOCKED = "blocked"
JOB_CANCELED = "canceled"
JOB_STATUSES = (JOB_QUEUED, JOB_IN_PROGRESS, JOB_DONE, JOB_BLOCKED, JOB_CANCELED)

STEP_PENDING = "pending"
STEP_IN_PROGRESS = "in_progress"
STEP_DONE = "done"
STEP_BLOCKED = "blocked"
STEP_SKIPPED = "skipped"
STEP_STATUSES = (STEP_PENDING, STEP_IN_PROGRESS, STEP_DONE, STEP_BLOCKED, STEP_SKIPPED)

# Чек-лист запуска нового сайта. Код шага стабилен: по нему обновляется статус.
STEP_TEMPLATE: tuple[tuple[str, str, str], ...] = (
    ("hosting", "Хостинг и аккаунт", "Создать аккаунт на hoster.by и привязать тариф"),
    ("dns", "Домен и DNS", "Поддомен платформы или A/CNAME-запись своего домена"),
    ("ssl", "SSL-сертификат", "Выпустить сертификат и включить HTTPS"),
    ("deploy", "Публикация сайта", "Развернуть сборку, проверить окружение и миграции"),
    ("mail", "Почта и уведомления", "Настроить отправителя, SMS и уведомления о заказах"),
    ("billing", "Тариф и оплата", "Выставить счёт и подтвердить оплату"),
    ("smoke", "Проверка магазина", "Открыть витрину, вход владельца, тестовый заказ"),
)

STEP_CODES = frozenset(code for code, _, _ in STEP_TEMPLATE)

DEPLOY_LABEL = {
    DEPLOY_NOT_STARTED: "Не запускался",
    DEPLOY_QUEUED: "В очереди",
    DEPLOY_IN_PROGRESS: "Публикуется",
    DEPLOY_DEPLOYED: "Работает",
    DEPLOY_FAILED: "Ошибка",
    DEPLOY_PAUSED: "Приостановлен",
}

JOB_LABEL = {
    JOB_QUEUED: "В очереди",
    JOB_IN_PROGRESS: "В работе",
    JOB_DONE: "Завершён",
    JOB_BLOCKED: "Заблокирован",
    JOB_CANCELED: "Отменён",
}

STEP_LABEL = {
    STEP_PENDING: "Ожидает",
    STEP_IN_PROGRESS: "В работе",
    STEP_DONE: "Готово",
    STEP_BLOCKED: "Проблема",
    STEP_SKIPPED: "Пропущен",
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def _fresh_steps() -> list[dict]:
    stamp = now().isoformat()
    return [
        {
            "code": code,
            "title": title,
            "detail": detail,
            "status": STEP_PENDING,
            "note": "",
            "updated_at": stamp,
        }
        for code, title, detail in STEP_TEMPLATE
    ]


def _active_job(db: Session, tenant_id: int) -> ProvisioningJob | None:
    return db.scalar(
        select(ProvisioningJob)
        .where(
            ProvisioningJob.tenant_id == tenant_id,
            ProvisioningJob.status.in_((JOB_QUEUED, JOB_IN_PROGRESS, JOB_BLOCKED)),
        )
        .order_by(ProvisioningJob.created_at.desc())
        .execution_options(skip_tenant_filter=True)
    )


def latest_job(db: Session, tenant_id: int) -> ProvisioningJob | None:
    return db.scalar(
        select(ProvisioningJob)
        .where(ProvisioningJob.tenant_id == tenant_id)
        .order_by(ProvisioningJob.created_at.desc())
        .execution_options(skip_tenant_filter=True)
    )


def _primary_domain(tenant: Tenant) -> TenantDomain | None:
    if not tenant.domains:
        return None
    return next((item for item in tenant.domains if item.is_primary), tenant.domains[0])


def _progress(steps: list[dict]) -> int:
    if not steps:
        return 0
    weights = {
        STEP_DONE: 1.0,
        STEP_SKIPPED: 1.0,
        STEP_IN_PROGRESS: 0.5,
        STEP_BLOCKED: 0.25,
        STEP_PENDING: 0.0,
    }
    return round(100 * sum(weights.get(item.get("status"), 0) for item in steps) / len(steps))


def job_payload(job: ProvisioningJob) -> dict:
    steps = job.steps or []
    done = sum(1 for item in steps if item.get("status") in (STEP_DONE, STEP_SKIPPED))
    return {
        "id": job.id,
        "tenant_id": job.tenant_id,
        "kind": job.kind,
        "status": job.status,
        "status_label": JOB_LABEL.get(job.status, job.status),
        "steps": steps,
        "progress": _progress(steps),
        "steps_done": done,
        "steps_total": len(steps),
        "note": job.note,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def state_payload(db: Session, tenant: Tenant) -> dict:
    job = latest_job(db, tenant.id)
    return {
        "tenant_id": tenant.id,
        "job": job_payload(job) if job else None,
        "template": [
            {"code": code, "title": title, "detail": detail}
            for code, title, detail in STEP_TEMPLATE
        ],
        "hosting": hosting_payload(tenant),
    }


def hosting_payload(tenant: Tenant) -> dict:
    domain = _primary_domain(tenant)
    return {
        "hosting_provider": tenant.hosting_provider,
        "hosting_tariff": tenant.hosting_tariff,
        "hosting_account": tenant.hosting_account,
        "deploy_status": tenant.deploy_status,
        "deploy_status_label": DEPLOY_LABEL.get(tenant.deploy_status, tenant.deploy_status),
        "deploy_url": tenant.deploy_url,
        "ops_note": tenant.ops_note,
        "primary_host": domain.host if domain else "",
        "ssl_status": domain.ssl_status if domain else "none",
        "dns_status": domain.dns_status if domain else "pending",
    }


def ensure_job(db: Session, tenant: Tenant) -> ProvisioningJob:
    """Возвращает активную задачу запуска или создаёт новую с чек-листом."""
    job = _active_job(db, tenant.id)
    if job:
        return job

    existing = latest_job(db, tenant.id)
    job = ProvisioningJob(
        tenant_id=tenant.id,
        kind="launch",
        status=JOB_QUEUED,
        steps=_fresh_steps(),
        note="",
        started_at=None,
        completed_at=None,
    )
    db.add(job)
    if tenant.deploy_status in (DEPLOY_NOT_STARTED, DEPLOY_FAILED):
        tenant.deploy_status = DEPLOY_QUEUED
    if not tenant.hosting_provider:
        tenant.hosting_provider = "hoster_by"
    if existing and existing.status == JOB_DONE:
        job.note = "Повторный запуск после завершённой задачи"
    db.flush()
    return job


def _sync_tenant(db: Session, tenant: Tenant, job: ProvisioningJob) -> None:
    if job.status in (JOB_QUEUED, JOB_IN_PROGRESS):
        if job.status == JOB_IN_PROGRESS:
            tenant.deploy_status = DEPLOY_IN_PROGRESS
        elif tenant.deploy_status == DEPLOY_NOT_STARTED:
            tenant.deploy_status = DEPLOY_QUEUED
    elif job.status == JOB_DONE:
        tenant.deploy_status = DEPLOY_DEPLOYED
    elif job.status == JOB_BLOCKED:
        tenant.deploy_status = DEPLOY_FAILED
    elif job.status == JOB_CANCELED:
        tenant.deploy_status = DEPLOY_PAUSED


def update_job(
    db: Session,
    job: ProvisioningJob,
    *,
    status_value: str | None = None,
    note: str | None = None,
) -> ProvisioningJob:
    if status_value is not None:
        if status_value not in JOB_STATUSES:
            raise HTTPException(status_code=422, detail="Неизвестный статус задачи")
        job.status = status_value
        if status_value == JOB_IN_PROGRESS and not job.started_at:
            job.started_at = now()
        if status_value in (JOB_DONE, JOB_CANCELED):
            job.completed_at = now()
        else:
            job.completed_at = None
    if note is not None:
        job.note = note.strip()

    tenant = db.get(Tenant, job.tenant_id)
    if tenant:
        _sync_tenant(db, tenant, job)
    job.updated_at = now()
    db.commit()
    db.refresh(job)
    return job


def update_step(
    db: Session,
    job: ProvisioningJob,
    code: str,
    *,
    status_value: str,
    note: str | None = None,
) -> ProvisioningJob:
    if code not in STEP_CODES:
        raise HTTPException(status_code=404, detail="Шаг не найден")
    if status_value not in STEP_STATUSES:
        raise HTTPException(status_code=422, detail="Неизвестный статус шага")

    steps = [dict(item) for item in (job.steps or [])]
    stamp = now().isoformat()
    found = False
    for item in steps:
        if item.get("code") != code:
            continue
        found = True
        item["status"] = status_value
        if note is not None:
            item["note"] = note.strip()
        item["updated_at"] = stamp
    if not found:
        raise HTTPException(status_code=404, detail="Шаг не найден")
    job.steps = steps

    statuses = {item.get("status") for item in steps}
    if statuses <= {STEP_DONE, STEP_SKIPPED}:
        job.status = JOB_DONE
        job.completed_at = now()
    elif STEP_BLOCKED in statuses:
        job.status = JOB_BLOCKED
    else:
        job.status = JOB_IN_PROGRESS
        job.started_at = job.started_at or now()
    job.updated_at = now()

    tenant = db.get(Tenant, job.tenant_id)
    if tenant:
        _sync_tenant(db, tenant, job)
    db.commit()
    db.refresh(job)
    return job


def update_hosting(db: Session, tenant: Tenant, changes: dict) -> Tenant:
    if "deploy_status" in changes and changes["deploy_status"] is not None:
        value = changes["deploy_status"]
        if value not in DEPLOY_STATUSES:
            raise HTTPException(status_code=422, detail="Неизвестный статус публикации")
        tenant.deploy_status = value
    for field in (
        "hosting_provider",
        "hosting_tariff",
        "hosting_account",
        "deploy_url",
        "ops_note",
    ):
        if field in changes and changes[field] is not None:
            setattr(tenant, field, str(changes[field]).strip())
    tenant.updated_at = now()
    db.commit()
    db.refresh(tenant)
    return tenant


def tenant_health(db: Session, tenant: Tenant, job: ProvisioningJob | None) -> dict:
    """Сводка состояния сайта для мониторинга платформы."""
    domain = _primary_domain(tenant)
    open_invoices = int(
        db.scalar(
            select(func.count(Invoice.id))
            .where(Invoice.tenant_id == tenant.id, Invoice.status == "open")
            .execution_options(skip_tenant_filter=True)
        )
        or 0
    )

    issues: list[str] = []
    if tenant.deploy_status == DEPLOY_FAILED:
        issues.append("Ошибка публикации")
    if tenant.deploy_status in (DEPLOY_NOT_STARTED,) and tenant.status == TENANT_ACTIVE:
        issues.append("Сайт не опубликован")
    if domain and domain.ssl_status not in ("active", "issued"):
        issues.append("SSL не активен")
    if domain and domain.dns_status not in ("ok", "active"):
        issues.append("DNS не подтверждён")
    if open_invoices:
        issues.append(f"Открытых счетов: {open_invoices}")
    if tenant.status in (TENANT_ONBOARDING,) and tenant.deploy_status == DEPLOY_DEPLOYED:
        issues.append("Оплата не подтверждена")

    if tenant.status == "suspended" or tenant.deploy_status == DEPLOY_FAILED:
        level = "error"
    elif issues:
        level = "attention"
    else:
        level = "ok"

    return {
        "tenant_id": tenant.id,
        "slug": tenant.slug,
        "name": tenant.name,
        "tenant_status": tenant.status,
        "deploy_status": tenant.deploy_status,
        "deploy_status_label": DEPLOY_LABEL.get(tenant.deploy_status, tenant.deploy_status),
        "deploy_url": tenant.deploy_url,
        "primary_host": domain.host if domain else "",
        "ssl_status": domain.ssl_status if domain else "none",
        "dns_status": domain.dns_status if domain else "pending",
        "open_invoices": open_invoices,
        "job_id": job.id if job else None,
        "job_status": job.status if job else None,
        "job_progress": _progress(job.steps or []) if job else 0,
        "level": level,
        "issues": issues,
    }


def overview(db: Session, limit: int = 50) -> dict:
    tenants = db.scalars(
        select(Tenant)
        .order_by(Tenant.updated_at.desc())
        .execution_options(skip_tenant_filter=True)
    ).all()

    # Оставляем только последнюю задачу по каждому магазину.
    latest: dict[int, ProvisioningJob] = {}
    for job in db.scalars(
        select(ProvisioningJob)
        .order_by(ProvisioningJob.created_at.desc())
        .execution_options(skip_tenant_filter=True)
    ).all():
        latest.setdefault(job.tenant_id, job)

    items = [tenant_health(db, tenant, latest.get(tenant.id)) for tenant in tenants]

    checks = uptime.summaries(db, [tenant.id for tenant in tenants])
    for item in items:
        summary = checks.get(item["tenant_id"]) or uptime.summarize([])
        item["uptime"] = summary
        if summary["last_ok"] is False:
            item["issues"].append("Сайт не отвечает")
            item["level"] = "error"
        elif summary["uptime_24h"] is not None and summary["uptime_24h"] < 99:
            item["issues"].append(f"Доступность {summary['uptime_24h']}%")
            if item["level"] == "ok":
                item["level"] = "attention"
        if summary["avg_latency_ms"] is not None and summary["avg_latency_ms"] > 3000:
            item["issues"].append(f"Медленный ответ: {summary['avg_latency_ms']} мс")
            if item["level"] == "ok":
                item["level"] = "attention"

    by_level = {"ok": 0, "attention": 0, "error": 0}
    for item in items:
        by_level[item["level"]] = by_level.get(item["level"], 0) + 1

    queue = [item for item in items if latest.get(item["tenant_id"]) and latest[item["tenant_id"]].status in (JOB_QUEUED, JOB_IN_PROGRESS, JOB_BLOCKED)]
    attention = [item for item in items if item["level"] != "ok"]

    return {
        "tenants_total": len(items),
        "deployed": sum(1 for item in items if item["deploy_status"] == DEPLOY_DEPLOYED),
        "by_status": {
            key: sum(1 for item in items if item["deploy_status"] == key)
            for key in DEPLOY_STATUSES
        },
        "by_level": by_level,
        "queue_total": len(queue),
        "attention_total": len(attention),
        "queue": queue[:limit],
        "attention": attention[:limit],
        "items": items[:limit],
    }
