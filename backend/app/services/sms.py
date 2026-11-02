"""Отправка SMS-кодов. Провайдер задаётся переменной SMS_PROVIDER."""

import logging
from dataclasses import dataclass

import requests

from app.config import settings


log = logging.getLogger("rybnaya.sms")


class SmsError(RuntimeError):
    pass


@dataclass
class SmsResult:
    sent: bool
    provider: str
    debug_code: str | None = None


def _send_console(phone: str, text: str) -> SmsResult:
    log.warning("SMS (console) → %s: %s", phone, text)
    return SmsResult(sent=True, provider="console")


def _send_smsby(phone: str, text: str) -> SmsResult:
    payload = {
        "phone": phone,
        "message": text,
        "sender": settings.sms_sender or None,
    }
    headers = {"Authorization": f"Bearer {settings.sms_api_token}", "Content-Type": "application/json"}
    try:
        response = requests.post(settings.sms_api_url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        log.error("SMS.BY error: %s", exc)
        raise SmsError("Не удалось отправить SMS. Попробуйте позже.") from exc
    return SmsResult(sent=True, provider="smsby")


def _send_websms(phone: str, text: str) -> SmsResult:
    payload = {
        "login": settings.sms_login,
        "password": settings.sms_password,
        "sender": settings.sms_sender,
        "recipients": [{"phone": phone}],
        "message": text,
    }
    try:
        response = requests.post(settings.sms_api_url, json=payload, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        log.error("WebSMS error: %s", exc)
        raise SmsError("Не удалось отправить SMS. Попробуйте позже.") from exc
    return SmsResult(sent=True, provider="websms")


def send_sms(phone: str, text: str) -> SmsResult:
    provider = (settings.sms_provider or "console").lower()
    if provider == "console":
        return _send_console(phone, text)
    if provider == "smsby":
        return _send_smsby(phone, text)
    if provider == "websms":
        return _send_websms(phone, text)
    raise SmsError(f"Неизвестный SMS-провайдер: {provider}")


def code_message(code: str, minutes: int, brand: str = "Рыбная лавка") -> str:
    return (
        f"Код подтверждения {brand}: {code}. Действует {minutes} мин. "
        f"Никому не сообщайте код. Если вы не запрашивали код, проигнорируйте SMS."
    )
