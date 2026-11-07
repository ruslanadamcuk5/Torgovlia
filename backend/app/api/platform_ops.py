"""API платформы: очередь запусков, хостинг и мониторинг сайтов."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.deps import require_platform
from app.models import (
    PlatformUser,
    ProvisioningJob,
    SupportTicket,
    TICKET_CLOSED,
    TICKET_OPEN,
    TICKET_PRIORITIES,
    Tenant,
)
from app.platform import alerts, ops
from app.schemas import (
    AlertSendIn,
    AlertSendOut,
    AlertsOut,
    HostingOut,
    HostingUpdateIn,
    OpsOverviewOut,
    ProvisioningJobOut,
    ProvisioningJobUpdateIn,
    ProvisioningStateOut,
    ProvisioningStepUpdateIn,
    SupportTicketIn,
    SupportTicketOut,
    SupportTicketUpdateIn,
)
from app.services.audit import audit


router = APIRouter(prefix="/platform", tags=["Платформа: запуск и хостинг"])


def _tenant_or_404(db: Session, tenant_id: int) -> Tenant:
    tenant = db.scalar(
        select(Tenant).where(Tenant.id == tenant_id).options(selectinload(Tenant.domains))
    )
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Арендатор не найден")
    return tenant


def _job_or_404(db: Session, job_id: int) -> ProvisioningJob:
    job = db.scalar(
        select(ProvisioningJob)
        .where(ProvisioningJob.id == job_id)
        .execution_options(skip_tenant_filter=True)
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
    return job


@router.get(
    "/ops/overview",
    response_model=OpsOverviewOut,
    summary="Мониторинг сайтов и очередь запусков",
)
def ops_overview(
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
):
    return ops.overview(db, limit=limit)


@router.get(
    "/alerts",
    response_model=AlertsOut,
    summary="Сводка проблем для оповещений",
)
def platform_alerts(
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    return alerts.digest(db)


@router.post(
    "/alerts/telegram",
    response_model=AlertSendOut,
    summary="Отправить сводку в Telegram",
)
def send_alerts_to_telegram(
    payload: AlertSendIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    data = alerts.digest(db)
    text = (
        "Torgovlia: тестовое сообщение. Оповещения платформы настроены."
        if payload.test
        else data["text"]
    )
    try:
        alerts.send_telegram(text)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    audit(
        db,
        "platform.alerts.telegram",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        entity="platform",
        entity_id="alerts",
        details={"test": payload.test, "count": data["total"]},
    )
    db.commit()
    return {
        "sent": True,
        "count": data["total"],
        "message": "Тестовое сообщение отправлено" if payload.test else "Сводка отправлена",
    }


@router.get(
    "/tenants/{tenant_id}/provisioning",
    response_model=ProvisioningStateOut,
    summary="Задача запуска и хостинг магазина",
)
def tenant_provisioning(
    tenant_id: int,
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenant = _tenant_or_404(db, tenant_id)
    return ops.state_payload(db, tenant)


@router.post(
    "/tenants/{tenant_id}/provisioning",
    response_model=ProvisioningStateOut,
    status_code=status.HTTP_201_CREATED,
    summary="Поставить магазин в очередь запуска",
)
def start_provisioning(
    tenant_id: int,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenant = _tenant_or_404(db, tenant_id)
    job = ops.ensure_job(db, tenant)
    audit(
        db,
        "tenant.provisioning.start",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=tenant.id,
        entity="provisioning_job",
        entity_id=str(job.id),
        details={"status": job.status},
    )
    db.commit()
    db.refresh(tenant)
    db.refresh(job)
    return ops.state_payload(db, tenant)


@router.get(
    "/tenants/{tenant_id}/support",
    response_model=list[SupportTicketOut],
    summary="Обращения и заметки поддержки",
)
def list_support_tickets(
    tenant_id: int,
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    _tenant_or_404(db, tenant_id)
    return db.scalars(
        select(SupportTicket)
        .where(SupportTicket.tenant_id == tenant_id)
        .order_by(
            case((SupportTicket.status == TICKET_OPEN, 0), else_=1),
            SupportTicket.created_at.desc(),
        )
        .execution_options(skip_tenant_filter=True)
    ).all()


@router.post(
    "/tenants/{tenant_id}/support",
    response_model=SupportTicketOut,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить обращение поддержки",
)
def create_support_ticket(
    tenant_id: int,
    payload: SupportTicketIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenant = _tenant_or_404(db, tenant_id)
    ticket = SupportTicket(
        tenant_id=tenant.id,
        subject=payload.subject.strip(),
        body=payload.body.strip(),
        priority=payload.priority,
        status=TICKET_OPEN,
        author=user.full_name or user.phone,
    )
    db.add(ticket)
    db.flush()
    audit(
        db,
        "tenant.support.create",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=tenant.id,
        entity="support_ticket",
        entity_id=str(ticket.id),
        details={"subject": ticket.subject, "priority": ticket.priority},
    )
    db.commit()
    db.refresh(ticket)
    return ticket


@router.patch(
    "/support/{ticket_id}",
    response_model=SupportTicketOut,
    summary="Изменить обращение поддержки",
)
def update_support_ticket(
    ticket_id: int,
    payload: SupportTicketUpdateIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    ticket = db.scalar(
        select(SupportTicket)
        .where(SupportTicket.id == ticket_id)
        .execution_options(skip_tenant_filter=True)
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Обращение не найдено")

    changes = payload.model_dump(exclude_unset=True)
    if "priority" in changes and changes["priority"] not in TICKET_PRIORITIES:
        raise HTTPException(status_code=422, detail="Неизвестный приоритет")
    if "status" in changes and changes["status"] not in (TICKET_OPEN, TICKET_CLOSED):
        raise HTTPException(status_code=422, detail="Неизвестный статус")
    if "body" in changes and changes["body"] is not None:
        ticket.body = changes["body"].strip()
    if "priority" in changes and changes["priority"] is not None:
        ticket.priority = changes["priority"]
    if "status" in changes and changes["status"] is not None:
        ticket.status = changes["status"]
        ticket.closed_at = ops.now() if ticket.status == TICKET_CLOSED else None
    ticket.updated_at = ops.now()
    audit(
        db,
        "tenant.support.update",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=ticket.tenant_id,
        entity="support_ticket",
        entity_id=str(ticket.id),
        details={key: str(value) for key, value in changes.items()},
    )
    db.commit()
    db.refresh(ticket)
    return ticket


@router.patch(
    "/provisioning/{job_id}",
    response_model=ProvisioningJobOut,
    summary="Изменить статус задачи запуска",
)
def update_provisioning_job(
    job_id: int,
    payload: ProvisioningJobUpdateIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    job = _job_or_404(db, job_id)
    job = ops.update_job(
        db, job, status_value=payload.status, note=payload.note
    )
    audit(
        db,
        "tenant.provisioning.update",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=job.tenant_id,
        entity="provisioning_job",
        entity_id=str(job.id),
        details={"status": job.status},
    )
    db.commit()
    return ops.job_payload(job)


@router.patch(
    "/provisioning/{job_id}/steps/{code}",
    response_model=ProvisioningJobOut,
    summary="Отметить шаг запуска",
)
def update_provisioning_step(
    job_id: int,
    code: str,
    payload: ProvisioningStepUpdateIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    job = _job_or_404(db, job_id)
    job = ops.update_step(
        db,
        job,
        code,
        status_value=payload.status,
        note=payload.note,
    )
    audit(
        db,
        "tenant.provisioning.step",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=job.tenant_id,
        entity="provisioning_step",
        entity_id=code,
        details={"status": payload.status},
    )
    db.commit()
    return ops.job_payload(job)


@router.patch(
    "/tenants/{tenant_id}/hosting",
    response_model=HostingOut,
    summary="Хостинг и адрес публикации",
)
def update_hosting(
    tenant_id: int,
    payload: HostingUpdateIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenant = _tenant_or_404(db, tenant_id)
    tenant = ops.update_hosting(
        db, tenant, payload.model_dump(exclude_unset=True)
    )
    audit(
        db,
        "tenant.hosting.update",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=tenant.id,
        entity="tenant",
        entity_id=str(tenant.id),
        details={"fields": sorted(payload.model_dump(exclude_unset=True))},
    )
    db.commit()
    return ops.hosting_payload(tenant)
