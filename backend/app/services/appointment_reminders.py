"""Напоминания клиентам о записи.

Проверка идёт по всем арендаторам сразу: её запускает планировщик платформы
(`POST /api/platform/ops/cron`) или админ магазина кнопкой у записи. Канал
выбирается автоматически: письмо, если у клиента есть email и настроен SMTP,
иначе SMS. В разработке SMS уходит в лог (провайдер `console`).

Напоминание отправляется один раз: отметка `appointment.reminder_sent_at`
защищает от повторов, даже если планировщик срабатывает каждые пять минут.
Данные не покидают арендатора: выборка идёт по его записям, а настройки
читаются из его `tenant_settings`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    APPOINTMENT_ACTIVE,
    Appointment,
    Tenant,
)
from app.platform.sync import is_enabled
from app.services.booking import utc_to_local
from app.services.notifications import send_email
from app.services.settings import settings_for_tenant
from app.services.sms import SmsError, send_sms


log = logging.getLogger("torgovlia.reminders")

DEFAULT_HOURS = 24
MAX_LOOKAHEAD_HOURS = 24 * 14
SERVICE_CODE = "appointment_reminders"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def reminder_hours(db: Session, tenant_id: int) -> int:
    value = int(settings_for_tenant(db, tenant_id).reminder_hours or DEFAULT_HOURS)
    return min(max(value, 1), MAX_LOOKAHEAD_HOURS)


def booking_link(tenant: Tenant | None) -> str:
    base = (settings.public_base_url or "").rstrip("/")
    slug = tenant.slug if tenant else ""
    return f"{base}/shop/{slug}/booking" if slug else f"{base}/booking"


def build_message(
    appointment: Appointment,
    brand: str,
    link: str,
    *,
    cancelled: bool = False,
) -> str:
    moment = utc_to_local(appointment.starts_at)
    date_label = moment.strftime("%d.%m.%Y")
    time_label = moment.strftime("%H:%M")
    who = f" у {appointment.specialist_name}" if appointment.specialist_name else ""
    if cancelled:
        return (
            f"{brand}: запись на «{appointment.service_title}» {date_label} в "
            f"{time_label}{who} отменена. Если это ошибка, запишитесь снова: {link}"
        )
    return (
        f"{brand}: напоминаем о записи на «{appointment.service_title}» "
        f"{date_label} в {time_label}{who}. Номер {appointment.number}. "
        f"Если планы изменились, отмените запись: {link}"
    )


def _deliver(appointment: Appointment, text: str, subject: str) -> str:
    """Отправляет напоминание и возвращает использованный канал."""
    if appointment.email and settings.smtp_host:
        send_email(appointment.email, subject, text)
        return "email"
    send_sms(appointment.phone, text[:300])
    return "sms"


def send_one(
    db: Session,
    appointment: Appointment,
    *,
    force: bool = False,
    cancelled: bool = False,
) -> dict:
    """Отправляет напоминание по одной записи.

    `force` нужен для ручной отправки из админки: он игнорирует отметку и
    статус сервиса, но не трогает завершённые и отменённые записи.
    """
    if appointment.reminder_sent_at and not force:
        return {"sent": False, "reason": "already_sent", "channel": ""}
    if appointment.status not in APPOINTMENT_ACTIVE and not cancelled:
        return {"sent": False, "reason": "inactive", "channel": ""}

    tenant = db.get(Tenant, appointment.tenant_id)
    if not force and (tenant is None or not is_enabled(db, appointment.tenant_id, SERVICE_CODE)):
        return {"sent": False, "reason": "service_off", "channel": ""}

    brand = tenant.name if tenant else "Запись"
    text = build_message(appointment, brand, booking_link(tenant), cancelled=cancelled)
    subject = f"Напоминание о записи {appointment.number}"
    try:
        channel = _deliver(appointment, text, subject)
    except (RuntimeError, SmsError, OSError) as exc:  # noqa: BLE001 — напоминание не должно ронять cron
        log.warning("Напоминание %s не отправлено: %s", appointment.number, exc)
        return {"sent": False, "reason": str(exc)[:200], "channel": ""}

    appointment.reminder_sent_at = _utcnow()
    db.commit()
    return {"sent": True, "reason": "", "channel": channel}


def send_due(db: Session, *, now: datetime | None = None, limit: int = 500) -> dict:
    """Находит записи, до которых осталось меньше настроенного окна, и шлёт SMS."""
    moment = now or _utcnow()
    horizon = moment + timedelta(hours=MAX_LOOKAHEAD_HOURS)
    rows = db.scalars(
        select(Appointment)
        .where(
            Appointment.status.in_(APPOINTMENT_ACTIVE),
            Appointment.reminder_sent_at.is_(None),
            Appointment.starts_at >= moment,
            Appointment.starts_at <= horizon,
        )
        .order_by(Appointment.starts_at)
        .limit(limit)
        .execution_options(skip_tenant_filter=True)
    ).all()

    sent = 0
    skipped = 0
    failed = 0
    for appointment in rows:
        hours = reminder_hours(db, appointment.tenant_id)
        if appointment.starts_at - moment > timedelta(hours=hours):
            skipped += 1
            continue
        result = send_one(db, appointment)
        if result["sent"]:
            sent += 1
        elif result["reason"] in ("service_off", "inactive", "already_sent"):
            skipped += 1
        else:
            failed += 1
    return {"checked": len(rows), "sent": sent, "skipped": skipped, "failed": failed}
