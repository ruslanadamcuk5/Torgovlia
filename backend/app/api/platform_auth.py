"""Вход сотрудников платформы. Отдельный контур авторизации от магазинов."""

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import client_ip, get_platform_user
from app.models import PlatformUser
from app.schemas import LoginIn, PlatformTokenOut, PlatformUserOut
from app.security import create_platform_token, verify_password


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
        raise HTTPException(status_code=400, detail="Неверный номер или пароль")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Доступ к платформе закрыт")
    _attempts.pop(key, None)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return PlatformTokenOut(
        access_token=create_platform_token(user.id, user.role),
        user=PlatformUserOut.model_validate(user),
    )


@router.get("/me", response_model=PlatformUserOut, summary="Текущий сотрудник платформы")
def me(user: PlatformUser = Depends(get_platform_user)):
    return user
