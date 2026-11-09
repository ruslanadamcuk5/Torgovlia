"""API платформы: очередь запусков, хостинг и мониторинг сайтов."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import case, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
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
from app.platform import alerts, ops, uptime
from app.schemas import (
    AlertSendIn,
    AlertSendOut,
    AlertsOut,
    CronRunOut,
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
    SupportReplyIn,
    SupportTemplateOut,
    UptimeRunOut,
    UptimeSummaryOut,
)
from app.services.audit import audit


router = APIRouter(prefix="/platform", tags=["Платформа: запуск и хостинг"])

# Готовые ответы поддержки: вставляются в обращение одним нажатием.
SUPPORT_TEMPLATES: tuple[tuple[str, str, str], ...] = (
    (
        "greeting",
        "Приветствие и уточнение",
        "Здравствуйте! Спасибо за обращение. Уточните, пожалуйста, что именно "
        "происходит и на какой странице — приложите скриншот, если возможно. "
        "Мы проверим и вернёмся с решением.",
    ),
    (
        "domain",
        "Подключение домена",
        "Чтобы подключить свой домен: 1) в карточке магазина откройте «Домены» и "
        "добавьте домен, отметьте его основным; 2) у регистратора создайте "
        "A-запись на IP сервера или CNAME на адрес платформы; 3) после обновления "
        "DNS мы выпустим SSL и проверим доступность. Обычно это занимает до 24 часов.",
    ),
    (
        "payment",
        "Счёт и оплата",
        "Счёт доступен в разделе «Биллинг» вашей админки. Оплатить можно по "
        "реквизитам из счёта или картой — после поступления оплаты тариф и услуги "
        "включаются автоматически. Если оплата уже прошла, пришлите номер счёта и "
        "дату платежа, мы сверим.",
    ),
    (
        "onboarding",
        "Помощь с запуском",
        "Давайте по шагам: 1) заполните название, контакты и реквизиты в "
        "«Настройках»; 2) загрузите логотип и выберите шаблон; 3) добавьте "
        "категории и первые товары; 4) проверьте оформление заказа; 5) включите "
        "нужные услуги. Если что-то не получается — напишите, на каком шаге "
        "остановились, и мы поможем.",
    ),
    (
        "resolved",
        "Закрытие обращения",
        "Проблема решена: изменения применены и проверены. Если заметите что-то "
        "ещё — просто ответьте на это обращение, мы продолжим. Спасибо, что "
        "пользуетесь платформой!",
    ),
)


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


@router.post(
    "/ops/checks",
    response_model=UptimeRunOut,
    summary="Проверить доступность сайтов",
)
def run_uptime_checks(
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
    tenant_id: int | None = Query(default=None, ge=1),
):
    tenant = _tenant_or_404(db, tenant_id) if tenant_id else None
    result = uptime.run_checks(db, [tenant] if tenant else None)
    audit(
        db,
        "platform.uptime.run",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=tenant_id,
        entity="platform",
        entity_id="uptime",
        details={
            "checked": result["checked"],
            "ok": result["ok"],
            "failed": result["failed"],
        },
    )
    db.commit()
    return result


@router.post(
    "/ops/cron",
    response_model=CronRunOut,
    summary="Плановая проверка доступности и отправка алертов",
)
def cron_checks(
    x_cron_token: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Вызывается внешним планировщиком, без входа пользователя.

    Токен задаётся в `CRON_TOKEN`; пока он пуст, эндпоинт выключен. Проверки
    идут по всем магазинам, сводка уходит в Telegram, если канал настроен.
    """
    expected = settings.cron_token.strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Планировщик не настроен: задайте CRON_TOKEN",
        )
    if not secrets.compare_digest(
        x_cron_token.strip().encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Неверный токен планировщика",
        )

    result = uptime.run_checks(db)
    data = alerts.digest(db)
    sent = False
    send_error = ""
    if data["total"] and data["telegram_configured"]:
        try:
            alerts.send_telegram(data["text"])
            sent = True
        except RuntimeError as exc:
            send_error = str(exc)[:500]

    audit(
        db,
        "platform.uptime.cron",
        actor="cron",
        entity="platform",
        entity_id="uptime",
        details={
            "checked": result["checked"],
            "failed": result["failed"],
            "alerts": data["total"],
            "telegram_sent": sent,
            "telegram_error": bool(send_error),
        },
    )
    db.commit()
    return {
        "checked": result["checked"],
        "ok": result["ok"],
        "failed": result["failed"],
        "alerts": data["total"],
        "errors": data["errors"],
        "warnings": data["warnings"],
        "telegram_configured": data["telegram_configured"],
        "telegram_sent": sent,
        "telegram_error": send_error,
        "text": data["text"],
    }


@router.get(
    "/tenants/{tenant_id}/uptime",
    response_model=UptimeSummaryOut,
    summary="Доступность и задержка магазина за 24 часа",
)
def tenant_uptime(
    tenant_id: int,
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    _tenant_or_404(db, tenant_id)
    return uptime.summary(db, tenant_id)


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


@router.get(
    "/support/templates",
    response_model=list[SupportTemplateOut],
    summary="Шаблоны ответов поддержки",
)
def list_support_templates(_: PlatformUser = Depends(require_platform)):
    return [
        {"code": code, "title": title, "body": body}
        for code, title, body in SUPPORT_TEMPLATES
    ]


@router.post(
    "/support/{ticket_id}/reply",
    response_model=SupportTicketOut,
    summary="Ответить на обращение поддержки",
)
def reply_support_ticket(
    ticket_id: int,
    payload: SupportReplyIn,
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

    stamp = ops.now().strftime("%d.%m.%Y %H:%M")
    reply = payload.body.strip()
    ticket.body = (ticket.body.rstrip() + f"\n\n— Ответ поддержки, {stamp}:\n{reply}").strip()
    if payload.close:
        ticket.status = TICKET_CLOSED
        ticket.closed_at = ops.now()
    ticket.updated_at = ops.now()
    audit(
        db,
        "platform.support.reply",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=ticket.tenant_id,
        entity="support_ticket",
        entity_id=str(ticket.id),
        details={"close": payload.close, "chars": len(reply)},
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
