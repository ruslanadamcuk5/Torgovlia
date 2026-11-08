"""Рассылки по клиентской базе: сегменты, аудитория и отправка.

Канал (email/SMS) задаётся в кампании. Получатели фиксируются на момент
запуска, чтобы статистика не менялась задним числом. Отправка идёт в фоне.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import (
    ORDER_CANCELLED,
    ORDER_COMPLETED,
    ORDER_REJECTED,
    ROLE_CUSTOMER,
    Campaign,
    CampaignRecipient,
    Order,
    User,
)
from app.security import format_phone, normalize_phone
from app.services.notifications import channels_status, send_email
from app.services.settings import settings_for_tenant
from app.services.sms import SmsError, send_sms


log = logging.getLogger("torgovlia.campaigns")

MAX_RECIPIENTS = 1000
EMAIL_BODY_LIMIT = 5000
SMS_BODY_LIMIT = 480


@dataclass(frozen=True)
class Segment:
    code: str
    title: str
    description: str


SEGMENTS: tuple[Segment, ...] = (
    Segment("all", "Все клиенты", "Все, у кого есть контакт для выбранного канала"),
    Segment("with_orders", "С покупками", "Хотя бы один заказ"),
    Segment("no_orders", "Без покупок", "Зарегистрированы, но ещё не заказывали"),
    Segment("recent", "Активные", "Покупали за последние 30 дней"),
    Segment("inactive", "Спящие", "Последний заказ был больше 60 дней назад"),
    Segment("vip", "VIP", "Купили на сумму от 200 BYN"),
    Segment("new", "Новые", "Первый заказ или регистрация за последние 30 дней"),
)
SEGMENT_BY_CODE = {segment.code: segment for segment in SEGMENTS}

CHANNEL_LABEL = {"email": "Email", "sms": "SMS"}


@dataclass
class Customer:
    key: str
    user_id: int | None
    name: str
    phone: str = ""
    email: str = ""
    orders: int = 0
    spent: Decimal = Decimal("0")
    first_order: datetime | None = None
    last_order: datetime | None = None
    registered_at: datetime | None = None
    consent: bool = True


@dataclass
class AudienceFilters:
    min_orders: int = 0
    min_spent: float = 0
    last_order_days: int = 0

    @classmethod
    def from_value(cls, value) -> "AudienceFilters":
        if isinstance(value, AudienceFilters):
            return value
        if isinstance(value, dict):
            return cls(
                min_orders=int(value.get("min_orders") or 0),
                min_spent=float(value.get("min_spent") or 0),
                last_order_days=int(value.get("last_order_days") or 0),
            )
        return cls()


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _collect(db: Session) -> list[Customer]:
    """Объединяет зарегистрированных клиентов и гостевые заказы по телефону."""
    customers: dict[str, Customer] = {}
    by_phone: dict[str, str] = {}

    users = db.scalars(
        select(User).where(User.role == ROLE_CUSTOMER, User.is_active.is_(True))
    ).all()
    for user in users:
        key = f"u{user.id}"
        customers[key] = Customer(
            key=key,
            user_id=user.id,
            name=user.full_name or "Клиент",
            phone=user.phone or "",
            email=(user.email or "").strip().lower(),
            registered_at=_aware(user.created_at),
            consent=bool(user.consent_personal_data),
        )
        if user.phone:
            by_phone[user.phone] = key

    orders = db.scalars(
        select(Order).where(Order.status.notin_((ORDER_CANCELLED, ORDER_REJECTED)))
    ).all()
    for order in orders:
        key = ""
        if order.user_id:
            key = f"u{order.user_id}"
            if key not in customers:
                owner = db.get(User, order.user_id)
                if owner is not None:
                    # Неактивный сотрудник или покупатель без согласия не попадает в базу.
                    continue
                key = ""
        phone = order.phone or ""
        if not key and phone in by_phone:
            key = by_phone[phone]
        if not key:
            key = f"g{phone}" if phone else f"o{order.id}"
            if key not in customers:
                customers[key] = Customer(
                    key=key,
                    user_id=None,
                    name=order.customer_name or "Клиент",
                    phone=phone,
                )
            if phone:
                by_phone.setdefault(phone, key)
        customer = customers[key]
        if not customer.name or customer.name == "Клиент":
            customer.name = order.customer_name or customer.name
        customer.orders += 1
        if order.status == ORDER_COMPLETED:
            customer.spent += Decimal(str(order.total_amount or 0))
        created = _aware(order.created_at)
        if created:
            if customer.first_order is None or created < customer.first_order:
                customer.first_order = created
            if customer.last_order is None or created > customer.last_order:
                customer.last_order = created
    return list(customers.values())


def _matches(customer: Customer, segment: str, filters: AudienceFilters) -> bool:
    now = datetime.now(timezone.utc)
    if not customer.consent:
        return False
    if segment == "with_orders" and customer.orders == 0:
        return False
    if segment == "no_orders" and customer.orders > 0:
        return False
    if segment == "recent":
        if not customer.last_order or customer.last_order < now - timedelta(days=30):
            return False
    if segment == "inactive":
        if not customer.last_order or customer.last_order >= now - timedelta(days=60):
            return False
    if segment == "vip" and customer.spent < Decimal("200"):
        return False
    if segment == "new":
        first = customer.first_order or customer.registered_at
        if not first or first < now - timedelta(days=30):
            return False
    if filters.min_orders and customer.orders < filters.min_orders:
        return False
    if filters.min_spent and customer.spent < Decimal(str(filters.min_spent)):
        return False
    if filters.last_order_days:
        if not customer.last_order or customer.last_order < now - timedelta(days=filters.last_order_days):
            return False
    return True


def _contact(customer: Customer, channel: str) -> str:
    if channel == "email":
        email = customer.email.strip()
        return email if "@" in email and "." in email.split("@")[-1] else ""
    if channel == "sms":
        try:
            return normalize_phone(customer.phone)
        except ValueError:
            return ""
    return ""


def audience(
    db: Session,
    channel: str,
    segment: str = "all",
    filters: AudienceFilters | dict | None = None,
) -> list[Customer]:
    if segment not in SEGMENT_BY_CODE:
        raise HTTPException(status_code=422, detail="Неизвестный сегмент")
    conf = AudienceFilters.from_value(filters or {})
    result = []
    for customer in _collect(db):
        if not _matches(customer, segment, conf):
            continue
        if not _contact(customer, channel):
            continue
        result.append(customer)
    result.sort(key=lambda item: (-item.spent, -item.orders, item.name.lower()))
    return result


def segment_counts(db: Session) -> list[dict]:
    customers = _collect(db)
    items = []
    for segment in SEGMENTS:
        email = sum(
            1 for c in customers if _matches(c, segment.code, AudienceFilters()) and _contact(c, "email")
        )
        sms = sum(
            1 for c in customers if _matches(c, segment.code, AudienceFilters()) and _contact(c, "sms")
        )
        items.append(
            {
                "code": segment.code,
                "title": segment.title,
                "description": segment.description,
                "email": email,
                "sms": sms,
            }
        )
    return items


def _sample(customer: Customer, channel: str) -> dict:
    contact = _contact(customer, channel)
    return {
        "name": customer.name,
        "contact": contact,
        "contact_label": format_phone(contact) if channel == "sms" else contact,
        "orders": customer.orders,
        "spent": float(customer.spent),
        "last_order": customer.last_order,
    }


def audience_payload(
    db: Session,
    channel: str,
    segment: str,
    filters: AudienceFilters | dict | None = None,
    sample_size: int = 8,
) -> dict:
    customers = audience(db, channel, segment, filters)
    return {
        "channel": channel,
        "segment": segment,
        "total": len(customers),
        "sample": [_sample(customer, channel) for customer in customers[:sample_size]],
    }


def personalize(text: str, name: str, shop: str) -> str:
    value = text or ""
    value = value.replace("{name}", name or "друг").replace("{имя}", name or "друг")
    value = value.replace("{shop}", shop).replace("{магазин}", shop)
    return value


def _channel_ready(channel: str) -> bool:
    status = channels_status()
    return bool(status.get(channel))


def create(db: Session, payload, actor: str) -> Campaign:
    _validate(payload.channel, payload.body)
    campaign = Campaign(
        name=(payload.name or "Новая рассылка").strip()[:160],
        channel=payload.channel,
        subject=(payload.subject or "").strip()[:200],
        body=payload.body,
        segment=payload.segment,
        filters=AudienceFilters.from_value(payload.filters).__dict__,
        status="draft",
        created_by=actor[:120],
    )
    db.add(campaign)
    db.flush()
    return campaign


def update(db: Session, campaign: Campaign, payload) -> Campaign:
    data = payload.model_dump(exclude_unset=True)
    channel = data.get("channel", campaign.channel)
    body = data.get("body", campaign.body)
    _validate(channel, body)
    if campaign.status not in ("draft", "cancelled"):
        raise HTTPException(status_code=409, detail="Отправленную рассылку нельзя изменить")
    for field_name in ("name", "channel", "subject", "body", "segment"):
        if field_name in data and data[field_name] is not None:
            setattr(campaign, field_name, data[field_name])
    if "filters" in data and data["filters"] is not None:
        campaign.filters = AudienceFilters.from_value(data["filters"]).__dict__
    if campaign.status == "cancelled":
        campaign.status = "draft"
        campaign.sent_at = None
    db.flush()
    return campaign


def _validate(channel: str, body: str) -> None:
    if channel not in CHANNEL_LABEL:
        raise HTTPException(status_code=422, detail="Неизвестный канал рассылки")
    limit = EMAIL_BODY_LIMIT if channel == "email" else SMS_BODY_LIMIT
    if not (body or "").strip():
        raise HTTPException(status_code=422, detail="Добавьте текст сообщения")
    if len(body) > limit:
        raise HTTPException(
            status_code=422,
            detail=f"Текст длиннее {limit} символов",
        )


def launch(db: Session, campaign: Campaign) -> Campaign:
    if campaign.status == "sending":
        raise HTTPException(status_code=409, detail="Рассылка уже отправляется")
    if campaign.status == "sent":
        raise HTTPException(status_code=409, detail="Рассылка уже отправлена")
    if not _channel_ready(campaign.channel) and not settings.demo_mode:
        hint = (
            "Настройте SMTP в переменных окружения, чтобы отправлять письма"
            if campaign.channel == "email"
            else "Подключите SMS-провайдера в переменных окружения"
        )
        raise HTTPException(status_code=400, detail=f"Канал не настроен. {hint}.")

    recipients = audience(
        db,
        campaign.channel,
        campaign.segment,
        campaign.filters or {},
    )[:MAX_RECIPIENTS]
    if not recipients:
        raise HTTPException(
            status_code=400,
            detail="В сегменте нет получателей с контактом для этого канала",
        )

    for customer in recipients:
        db.add(
            CampaignRecipient(
                tenant_id=campaign.tenant_id,
                campaign_id=campaign.id,
                user_id=customer.user_id,
                name=customer.name[:120],
                contact=_contact(customer, campaign.channel),
            )
        )
    campaign.status = "sending"
    campaign.recipients_count = len(recipients)
    campaign.sent_count = 0
    campaign.failed_count = 0
    campaign.skipped_count = 0
    campaign.demo_count = 0
    campaign.sent_at = None
    db.flush()

    threading.Thread(
        target=_deliver_campaign,
        args=(campaign.id,),
        daemon=True,
    ).start()
    return campaign


def _deliver_campaign(campaign_id: int) -> None:
    db = SessionLocal()
    try:
        campaign = db.get(Campaign, campaign_id)
        if not campaign:
            return
        shop = settings_for_tenant(db, campaign.tenant_id).brand_name
        ready = _channel_ready(campaign.channel)
        demo = settings.demo_mode and not ready
        sent = failed = demo_sent = 0
        recipients = db.scalars(
            select(CampaignRecipient)
            .where(CampaignRecipient.campaign_id == campaign_id)
            .order_by(CampaignRecipient.id)
        ).all()
        for recipient in recipients:
            text = personalize(campaign.body, recipient.name, shop)
            subject = personalize(campaign.subject, recipient.name, shop) or campaign.name
            try:
                if demo:
                    log.info(
                        "Демо-рассылка %s → %s: %s",
                        campaign.channel,
                        recipient.contact,
                        text[:120],
                    )
                    recipient.status = "demo"
                    demo_sent += 1
                elif campaign.channel == "email":
                    send_email(recipient.contact, subject[:200], text)
                    recipient.status = "sent"
                    sent += 1
                else:
                    send_sms(recipient.contact, text[:SMS_BODY_LIMIT])
                    recipient.status = "sent"
                    sent += 1
                recipient.sent_at = datetime.now(timezone.utc)
            except (RuntimeError, OSError, SmsError, ValueError) as exc:
                log.warning(
                    "Не удалось отправить %s на %s: %s",
                    campaign.channel,
                    recipient.contact,
                    exc,
                )
                recipient.status = "failed"
                recipient.error = str(exc)[:255]
                failed += 1
            db.commit()
        campaign = db.get(Campaign, campaign_id)
        if campaign:
            campaign.status = "sent"
            campaign.sent_count = sent + demo_sent
            campaign.failed_count = failed
            campaign.demo_count = demo_sent
            campaign.sent_at = datetime.now(timezone.utc)
            db.commit()
    except Exception:  # noqa: BLE001 — фон не должен оставлять «отправляется»
        log.exception("Рассылка %s не завершилась", campaign_id)
        db.rollback()
        campaign = db.get(Campaign, campaign_id)
        if campaign:
            campaign.status = "sent"
            campaign.sent_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


def serialize(campaign: Campaign) -> dict:
    return {
        "id": campaign.id,
        "name": campaign.name,
        "channel": campaign.channel,
        "channel_label": CHANNEL_LABEL.get(campaign.channel, campaign.channel),
        "subject": campaign.subject,
        "body": campaign.body,
        "segment": campaign.segment,
        "segment_title": SEGMENT_BY_CODE.get(campaign.segment, SEGMENTS[0]).title,
        "filters": campaign.filters or {},
        "status": campaign.status,
        "recipients_count": campaign.recipients_count,
        "sent_count": campaign.sent_count,
        "failed_count": campaign.failed_count,
        "skipped_count": campaign.skipped_count,
        "demo_count": campaign.demo_count,
        "created_by": campaign.created_by,
        "scheduled_at": campaign.scheduled_at,
        "sent_at": campaign.sent_at,
        "created_at": campaign.created_at,
    }


def recipients_payload(db: Session, campaign: Campaign, limit: int = 100) -> dict:
    rows = db.scalars(
        select(CampaignRecipient)
        .where(CampaignRecipient.campaign_id == campaign.id)
        .order_by(CampaignRecipient.id)
        .limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": row.id,
                "name": row.name,
                "contact": row.contact,
                "contact_label": format_phone(row.contact)
                if campaign.channel == "sms"
                else row.contact,
                "status": row.status,
                "error": row.error,
                "sent_at": row.sent_at,
            }
            for row in rows
        ],
        "total": campaign.recipients_count,
    }
