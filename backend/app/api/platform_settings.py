"""Глобальные настройки платформы: бренд, контакты, лимиты и режим набора."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_platform
from app.models import PlatformUser
from app.platform import settings as platform_settings
from app.schemas import PlatformSettingsIn, PlatformSettingsOut
from app.services.audit import audit


router = APIRouter(prefix="/platform/settings", tags=["Платформа: настройки"])


@router.get("", response_model=PlatformSettingsOut, summary="Глобальные настройки платформы")
def read_settings(
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    row = platform_settings.get_row(db)
    return {**platform_settings.get_config(db), "updated_at": row.updated_at}


@router.patch("", response_model=PlatformSettingsOut, summary="Изменить глобальные настройки")
def update_settings(
    payload: PlatformSettingsIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    changes = payload.model_dump(exclude_unset=True)
    config, updated_at = platform_settings.update_config(db, changes)
    audit(
        db,
        "platform.settings.update",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        entity="platform_settings",
        entity_id="1",
        details={key: str(value) for key, value in changes.items()},
    )
    db.commit()
    return {**config, "updated_at": updated_at}
