"""Уведомления владельца магазина о заказах.

Отправка идёт в фоне, чтобы оформление брони не ждало внешние сервисы.
Каналы необязательные: Telegram (бот платформы + чат магазина), SMS и email.
"""

from __future__ import annotations

import logging
import smtplib
import threading
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Order
from app.platform.alerts import send_telegram_to
from app.security import format_phone, normalize_phone
from app.services.settings import get_settings_model
from app.services.sms import SmsError, send_sms


log = logging.getLogger("torgovlia.notifications")

NEW = "new"
CANCELLED = "cancelled"


def channels_status() -> dict:
    return {
        "telegram": bool(settings.telegram_bot_token),
        "sms": (settings.sms_provider or "console").lower() != "console",
        "email": bool(settings.smtp_host and (settings.smtp_from or settings.smtp_user)),
    }


def _fulfillment(order: Order) -> str:
    if order.fulfillment == "delivery":
        zone = f" · {order.delivery_zone_name}" if order.delivery_zone_name else ""
        return f"доставка{zone}"
    return "самовывоз"


def build_message(order: Order, event: str) -> tuple[str, str]:
    """Возвращает (текст, тема письма)."""
    date_label = order.pickup_date.strftime("%d.%m.%Y")
    amount = f"{float(order.total_amount):.2f} BYN".replace(".", ",")
    items = len(order.items or [])
    if event == CANCELLED:
        text = (
            f"❌ Клиент отменил бронь {order.number}\n"
            f"Сумма: {amount}\n"
            f"Клиент: {order.customer_name}, {format_phone(order.phone)}\n"
            f"Когда: {date_label} в {order.pickup_time} · {_fulfillment(order)}"
        )
        return text, f"Бронь {order.number} отменена"

    address = f"\nАдрес: {order.delivery_address}" if order.fulfillment == "delivery" and order.delivery_address else ""
    text = (
        f"🛒 Новая бронь {order.number}\n"
        f"Сумма: {amount}\n"
        f"Клиент: {order.customer_name}, {format_phone(order.phone)}\n"
        f"Когда: {date_label} в {order.pickup_time} · {_fulfillment(order)}\n"
        f"Позиций: {items}{address}"
    )
    return text, f"Новая бронь {order.number} на {amount}"


def send_email(target: str, subject: str, text: str) -> None:
    if not settings.smtp_host:
        raise RuntimeError("SMTP не настроен")
    sender = settings.smtp_from or settings.smtp_user
    if not sender:
        raise RuntimeError("SMTP не настроен: SMTP_FROM")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = target
    message["Subject"] = subject
    message.set_content(text)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_tls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)


def _deliver(jobs: list[tuple[str, str, str, str]]) -> None:
    for channel, target, subject, text in jobs:
        try:
            if channel == "telegram":
                send_telegram_to(target, text)
            elif channel == "sms":
                send_sms(target, text[:300])
            elif channel == "email":
                send_email(target, subject, text)
        except (RuntimeError, SmsError, OSError) as exc:  # noqa: BLE001 — уведомление не должно ронять заказ
            log.warning("Не удалось отправить %s на %s: %s", channel, target, exc)


def _jobs_for(db: Session, order: Order, event: str) -> list[tuple[str, str, str, str]]:
    conf = get_settings_model(db)
    if event == NEW and not conf.notify_on_new_order:
        return []
    if event == CANCELLED and not conf.notify_on_cancel:
        return []
    text, subject = build_message(order, event)
    jobs: list[tuple[str, str, str, str]] = []
    if conf.notify_telegram_chat.strip():
        jobs.append(("telegram", conf.notify_telegram_chat.strip(), subject, text))
    if conf.notify_sms_phone.strip():
        try:
            phone = normalize_phone(conf.notify_sms_phone)
        except ValueError:
            phone = ""
        if phone:
            jobs.append(("sms", phone, subject, text))
    if conf.notify_email.strip():
        jobs.append(("email", conf.notify_email.strip(), subject, text))
    return jobs


def notify_order(db: Session, order: Order, event: str) -> None:
    """Ставит уведомление в фоновую отправку. Ошибки только логируются."""
    try:
        jobs = _jobs_for(db, order, event)
    except Exception as exc:  # noqa: BLE001
        log.warning("Не удалось подготовить уведомление по %s: %s", order.number, exc)
        return
    if jobs:
        threading.Thread(target=_deliver, args=(jobs,), daemon=True).start()


def test_channel(channel: str, target: str) -> None:
    text = "Torgovlia: проверка уведомлений магазина. Всё работает."
    subject = "Проверка уведомлений Torgovlia"
    if channel == "telegram":
        send_telegram_to(target, text)
    elif channel == "sms":
        send_sms(normalize_phone(target), text)
    elif channel == "email":
        send_email(target, subject, text)
    else:
        raise ValueError("Неизвестный канал")
