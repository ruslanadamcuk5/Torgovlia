"""Вход сотрудников платформы. Отдельный контур авторизации от магазинов."""

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import client_ip, get_platform_user
from app.models import PlatformUser
from app.platform import totp
from app.schemas import (
    LoginIn,
    PlatformTokenOut,
    PlatformUserOut,
    TwoFactorCodeIn,
    TwoFactorEnableOut,
    TwoFactorSetupOut,
    TwoFactorStatusOut,
)
from app.security import create_platform_token, verify_password
from app.services.audit import audit


router = APIRouter(prefix="/platform/auth", tags=["Платформа: вход"])

_WINDOW_SECONDS = 15 * 60
_MAX_ATTEMPTS = 10
_attempts: dict[str, list[float]] = {}


def _key(phone: str, ip: str) -> str:
    return f"platform:{phone}:{ip}"


def _check_limit(key: str) -> None:
    now = time.monotonic()
    recent = [stamp for stamp in _attempts.get(key, []) if now - stamp < _WINDOW_SECONDS]
    _attempts[key] = recent
    if len(recent) >= _MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Слишком много попыток входа. Попробуйте через 15 минут.")


@router.post("/login", response_model=PlatformTokenOut, summary="Вход в панель платформы")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    key = _key(payload.phone, client_ip(request))
    _check_limit(key)
    user = db.scalar(select(PlatformUser).where(PlatformUser.phone == payload.phone))
    if not user or not verify_password(payload.password, user.password_hash):
        _attempts.setdefault(key, []).append(time.monotonic())
        audit(
            db,
            "platform.login.failed",
            actor=payload.phone,
            entity="platform_user",
            details={"ip": client_ip(request), "reason": "bad_credentials"},
        )
        db.commit()
        raise HTTPException(status_code=400, detail="Неверный номер или пароль")
    if not user.is_active:
        audit(
            db,
            "platform.login.blocked",
            actor=user.full_name or user.phone,
            platform_user_id=user.id,
            entity="platform_user",
            entity_id=str(user.id),
            details={"ip": client_ip(request), "reason": "inactive"},
        )
        db.commit()
        raise HTTPException(status_code=403, detail="Доступ к платформе закрыт")
    if user.totp_enabled:
        code = (payload.totp_code or "").strip()
        if not code:
            raise HTTPException(
                status_code=428,
                detail="Введите код двухфакторной аутентификации из приложения.",
            )
        method = None
        if totp.verify(totp.decrypt_secret(user.totp_secret), code):
            method = "totp"
        elif _consume_recovery(user, code):
            method = "recovery"
        if not method:
            _attempts.setdefault(key, []).append(time.monotonic())
            audit(
                db,
                "platform.login.failed",
                actor=user.full_name or user.phone,
                platform_user_id=user.id,
                entity="platform_user",
                entity_id=str(user.id),
                details={"ip": client_ip(request), "reason": "bad_totp"},
            )
            db.commit()
            raise HTTPException(status_code=401, detail="Неверный код двухфакторной аутентификации")
    else:
        method = "password"

    _attempts.pop(key, None)
    user.last_login_at = datetime.now(timezone.utc)
    audit(
        db,
        "platform.login",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        entity="platform_user",
        entity_id=str(user.id),
        details={"ip": client_ip(request), "role": user.role, "method": method},
    )
    db.commit()
    return PlatformTokenOut(
        access_token=create_platform_token(user.id, user.role),
        user=PlatformUserOut.model_validate(user),
    )


@router.get("/me", response_model=PlatformUserOut, summary="Текущий сотрудник платформы")
def me(user: PlatformUser = Depends(get_platform_user)):
    return user


def _consume_recovery(user: PlatformUser, code: str) -> bool:
    digest = totp.hash_recovery_code(code)
    hashes = list(user.totp_recovery_hashes or [])
    if digest not in hashes:
        return False
    hashes.remove(digest)
    user.totp_recovery_hashes = hashes
    return True


@router.get("/2fa", response_model=TwoFactorStatusOut, summary="Состояние 2FA")
def two_factor_status(user: PlatformUser = Depends(get_platform_user)):
    return {
        "enabled": user.totp_enabled,
        "pending": bool(user.totp_secret) and not user.totp_enabled,
    }


@router.post("/2fa/setup", response_model=TwoFactorSetupOut, summary="Начать настройку 2FA")
def two_factor_setup(
    user: PlatformUser = Depends(get_platform_user),
    db: Session = Depends(get_db),
):
    if user.totp_enabled:
        raise HTTPException(status_code=409, detail="2FA уже включена")
    secret = totp.generate_secret()
    user.totp_secret = totp.encrypt_secret(secret)
    user.totp_enabled = False
    audit(
        db,
        "platform.2fa.setup",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        entity="platform_user",
        entity_id=str(user.id),
    )
    db.commit()
    return {"secret": secret, "uri": totp.provisioning_uri(secret, user.phone)}


@router.post("/2fa/enable", response_model=TwoFactorEnableOut, summary="Включить 2FA")
def two_factor_enable(
    payload: TwoFactorCodeIn,
    user: PlatformUser = Depends(get_platform_user),
    db: Session = Depends(get_db),
):
    if user.totp_enabled:
        raise HTTPException(status_code=409, detail="2FA уже включена")
    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="Сначала начните настройку 2FA")
    if not totp.verify(totp.decrypt_secret(user.totp_secret), payload.code):
        raise HTTPException(status_code=400, detail="Неверный код. Проверьте время на телефоне.")

    codes = totp.generate_recovery_codes()
    user.totp_enabled = True
    user.totp_recovery_hashes = [totp.hash_recovery_code(code) for code in codes]
    audit(
        db,
        "platform.2fa.enable",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        entity="platform_user",
        entity_id=str(user.id),
    )
    db.commit()
    return {"recovery_codes": codes}


@router.post("/2fa/disable", summary="Выключить 2FA")
def two_factor_disable(
    payload: TwoFactorCodeIn,
    user: PlatformUser = Depends(get_platform_user),
    db: Session = Depends(get_db),
):
    if not user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA не включена")
    valid = totp.verify(totp.decrypt_secret(user.totp_secret), payload.code) or _consume_recovery(
        user, payload.code
    )
    if not valid:
        raise HTTPException(status_code=400, detail="Неверный код 2FA или резервный код")
    user.totp_enabled = False
    user.totp_secret = None
    user.totp_recovery_hashes = []
    audit(
        db,
        "platform.2fa.disable",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        entity="platform_user",
        entity_id=str(user.id),
    )
    db.commit()
    return {"ok": True}
