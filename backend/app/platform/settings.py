"""Глобальные настройки платформы, хранимые в БД."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import PlatformSetting


DEFAULTS: dict = {
    "brand_name": "Torgovlia",
    "support_email": "hello@torgovlia.by",
    "support_phone": "",
    "default_plan_code": "start",
    "allow_signups": True,
    "max_tenants": 0,
    "maintenance_notice": "",
    "payment_instructions": (
        "Переведите сумму по реквизитам платформы и укажите номер счёта в назначении платежа. "
        "После подтверждения оплаты тариф и сервисы включатся автоматически."
    ),
    "sms_sender": "TORGOVLIA",
}


def get_row(db: Session) -> PlatformSetting:
    row = db.get(PlatformSetting, 1)
    if not row:
        row = PlatformSetting(id=1, data=dict(DEFAULTS))
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def get_config(db: Session) -> dict:
    row = db.get(PlatformSetting, 1)
    stored = row.data if row and isinstance(row.data, dict) else {}
    return {**DEFAULTS, **stored}


def update_config(db: Session, changes: dict) -> tuple[dict, datetime]:
    row = get_row(db)
    merged = {**DEFAULTS, **(row.data or {}), **{key: value for key, value in changes.items() if value is not None}}
    row.data = merged
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return merged, row.updated_at
