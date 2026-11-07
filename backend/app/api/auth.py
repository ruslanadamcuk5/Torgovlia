import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import client_ip, get_current_user, phone_from_token
from app.models import (
    ROLE_ADMIN,
    ROLE_CUSTOMER,
    PhoneVerification,
    User,
)
from app.schemas import (
    LoginIn,
    PasswordChangeIn,
    PasswordResetIn,
    PhoneConfirmIn,
    PhoneConfirmOut,
    PhoneLoginIn,
    PhoneRequestIn,
    PhoneRequestOut,
    ProfileUpdateIn,
    RegisterIn,
    TokenOut,
    UserOut,
)
from app.security import (
    check_sms_code,
    create_access_token,
    create_phone_token,
    decode_token,
    format_phone,
    generate_sms_code,
    hash_password,
    hash_sms_code,
    normalize_phone,
    validate_password,
    verify_password,
)
from app.serializers import order_payload  # noqa: F401  (kept for type imports)
from app.services.audit import audit
from app.services.settings import get_settings_model
from app.services.sms import SmsError, code_message, send_sms
from app.tenancy import current_tenant, current_tenant_id


router = APIRouter(prefix="/auth", tags=["Авторизация"])

# Простое ограничение перебора пароля. Для нескольких процессов за reverse-proxy
# дополнительно настройте rate limiting на уровне nginx.
_LOGIN_WINDOW_SECONDS = 15 * 60
_LOGIN_MAX_ATTEMPTS = 10
_login_attempts: dict[str, list[float]] = {}


def _login_key(phone: str, ip: str) -> str:
    return f"{phone}:{ip}"


def _check_login_limit(key: str) -> None:
    now = time.monotonic()
    attempts = [stamp for stamp in _login_attempts.get(key, []) if now - stamp < _LOGIN_WINDOW_SECONDS]
    _login_attempts[key] = attempts
    if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Слишком много попыток входа. Попробуйте через 15 минут.")


def _remember_failed_login(key: str) -> None:
    _login_attempts.setdefault(key, []).append(time.monotonic())


def _tenant_id() -> int:
    tenant = current_tenant()
    if not tenant:
        raise HTTPException(status_code=404, detail="Магазин не найден. Проверьте адрес сайта.")
    return tenant.id


def _user_by_phone(db: Session, phone: str) -> User | None:
    return db.scalar(
        select(User).where(User.phone == phone, User.tenant_id == _tenant_id())
    )


def _issue(user: User) -> TokenOut:
    user.last_login_at = datetime.now(timezone.utc)
    return TokenOut(access_token=create_access_token(user.id, user.role), user=UserOut.model_validate(user))


@router.post("/phone/request", response_model=PhoneRequestOut, summary="Запросить SMS-код")
def request_code(payload: PhoneRequestIn, request: Request, db: Session = Depends(get_db)):
    phone = payload.phone
    now = datetime.now(timezone.utc)
    user = _user_by_phone(db, phone)

    if payload.purpose == "register" and user:
        raise HTTPException(status_code=400, detail="Этот номер уже зарегистрирован. Войдите в аккаунт.")
    if payload.purpose in ("login", "reset") and not user:
        raise HTTPException(status_code=400, detail="Номер не найден. Зарегистрируйтесь или оформите заказ без регистрации.")
    if user and not user.is_active:
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован. Свяжитесь с павильоном.")

    last = db.scalar(
        select(PhoneVerification)
        .where(PhoneVerification.phone == phone)
        .order_by(PhoneVerification.created_at.desc())
        .limit(1)
    )
    if last:
        elapsed = (now - last.created_at).total_seconds()
        if elapsed < settings.sms_cooldown_seconds:
            wait = int(settings.sms_cooldown_seconds - elapsed)
            raise HTTPException(
                status_code=429,
                detail=f"Повторно отправить код можно через {wait} сек.",
                headers={"Retry-After": str(wait)},
            )

    hour_ago = now - timedelta(hours=1)
    recent = db.scalar(
        select(func.count(PhoneVerification.id)).where(
            PhoneVerification.phone == phone, PhoneVerification.created_at >= hour_ago
        )
    ) or 0
    if recent >= settings.sms_max_per_hour:
        raise HTTPException(status_code=429, detail="Слишком много запросов кода. Попробуйте через час.")

    verification_id = str(uuid.uuid4())
    code = generate_sms_code()
    ttl = max(2, settings.sms_code_ttl_minutes)
    row = PhoneVerification(
        id=verification_id,
        phone=phone,
        code_hash=hash_sms_code(code, verification_id),
        purpose=payload.purpose,
        expires_at=now + timedelta(minutes=ttl),
        ip=client_ip(request),
    )
    db.add(row)
    db.commit()

    brand = get_settings_model(db).brand_name
    try:
        send_sms(phone, code_message(code, ttl, brand))
    except SmsError as exc:
        db.delete(row)
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Демо-режим: при консольном SMS-провайдере код можно показать в интерфейсе,
    # чтобы проверить регистрацию и оформление заказа без реальной SMS-отправки.
    debug_code = None
    if settings.sms_expose_code and settings.sms_provider == "console":
        debug_code = code

    return PhoneRequestOut(
        verification_id=verification_id,
        phone=phone,
        phone_formatted=format_phone(phone),
        expires_in=ttl * 60,
        sms_sent=True,
        debug_code=debug_code,
        message=f"Код отправлен на {format_phone(phone)}",
    )


@router.post("/phone/confirm", response_model=PhoneConfirmOut, summary="Подтвердить SMS-код")
def confirm_code(payload: PhoneConfirmIn, db: Session = Depends(get_db)):
    row = db.get(PhoneVerification, payload.verification_id)
    if not row:
        raise HTTPException(status_code=400, detail="Заявка не найдена. Запросите новый код.")
    if row.is_used:
        raise HTTPException(status_code=400, detail="Код уже использован. Запросите новый.")
    if row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Код истёк. Запросите новый.")
    if row.attempts >= 5:
        raise HTTPException(status_code=429, detail="Слишком много попыток. Запросите новый код.")

    code = payload.code.strip()
    if not check_sms_code(code, row.id, row.code_hash):
        row.attempts += 1
        db.commit()
        left = 5 - row.attempts
        raise HTTPException(status_code=400, detail=f"Неверный код. Осталось попыток: {max(0, left)}")

    row.is_used = True
    db.commit()

    return PhoneConfirmOut(
        phone_token=create_phone_token(row.phone, row.purpose),
        phone=row.phone,
        phone_formatted=format_phone(row.phone),
        purpose=row.purpose,
        expires_in=settings.phone_token_minutes * 60,
    )


@router.post("/register", response_model=TokenOut, summary="Регистрация после подтверждения номера")
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    phone = phone_from_token(payload.phone_token)
    token_data = decode_token(payload.phone_token) or {}
    if token_data.get("purpose") not in ("register", "login"):
        raise HTTPException(status_code=400, detail="Подтвердите номер заново")

    if _user_by_phone(db, phone):
        raise HTTPException(status_code=400, detail="Этот номер уже зарегистрирован")

    try:
        validate_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = User(
        tenant_id=_tenant_id(),
        phone=phone,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        email=str(payload.email) if payload.email else None,
        role=ROLE_CUSTOMER,
        is_phone_verified=True,
        consent_personal_data=payload.consent_personal_data,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    audit(
        db,
        "user.register",
        actor=phone,
        user_id=user.id,
        tenant_id=user.tenant_id,
        entity="user",
        entity_id=str(user.id),
    )
    db.commit()
    return _issue(user)


def _login_audit(
    db: Session,
    action: str,
    phone: str,
    request: Request,
    user: User | None = None,
    reason: str = "",
) -> None:
    details = {"ip": client_ip(request)}
    if reason:
        details["reason"] = reason
    audit(
        db,
        action,
        actor=(user.full_name or user.phone) if user else phone,
        user_id=user.id if user else None,
        tenant_id=user.tenant_id if user else current_tenant_id(),
        entity="user",
        entity_id=str(user.id) if user else None,
        details=details,
    )
    db.commit()


@router.post("/login", response_model=TokenOut, summary="Вход по телефону и паролю")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    key = _login_key(payload.phone, client_ip(request))
    _check_login_limit(key)
    user = _user_by_phone(db, payload.phone)
    if not user or not verify_password(payload.password, user.password_hash):
        _remember_failed_login(key)
        _login_audit(db, "user.login.failed", payload.phone, request, reason="bad_credentials")
        raise HTTPException(status_code=400, detail="Неверный номер или пароль")
    if not user.is_active:
        _login_audit(db, "user.login.blocked", payload.phone, request, user=user, reason="inactive")
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован")
    if not user.is_phone_verified:
        _login_audit(db, "user.login.blocked", payload.phone, request, user=user, reason="unverified")
        raise HTTPException(status_code=403, detail="Подтвердите номер телефона")
    _login_attempts.pop(key, None)
    _login_audit(db, "user.login", payload.phone, request, user=user)
    return _issue(user)


@router.post("/login/phone", response_model=TokenOut, summary="Вход по подтверждённому номеру")
def login_by_phone(payload: PhoneLoginIn, db: Session = Depends(get_db)):
    phone = phone_from_token(payload.phone_token)
    token_data = decode_token(payload.phone_token) or {}
    if token_data.get("purpose") not in ("login", "register"):
        raise HTTPException(status_code=400, detail="Подтвердите номер заново")
    user = _user_by_phone(db, phone)
    if not user:
        raise HTTPException(status_code=404, detail="Номер не зарегистрирован")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован")
    user.is_phone_verified = True
    return _issue(user)


@router.post("/password/reset", summary="Сброс пароля после подтверждения номера")
def reset_password(payload: PasswordResetIn, db: Session = Depends(get_db)):
    phone = phone_from_token(payload.phone_token)
    token_data = decode_token(payload.phone_token) or {}
    if token_data.get("purpose") != "reset":
        raise HTTPException(status_code=400, detail="Подтвердите номер заново")
    user = _user_by_phone(db, phone)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    try:
        validate_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    user.password_hash = hash_password(payload.password)
    db.commit()
    audit(
        db,
        "user.password_reset",
        actor=phone,
        user_id=user.id,
        tenant_id=user.tenant_id,
        entity="user",
        entity_id=str(user.id),
    )
    db.commit()
    return {"ok": True, "message": "Пароль обновлён. Войдите с новым паролем."}


@router.get("/me", response_model=UserOut, summary="Текущий пользователь")
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut, summary="Обновить профиль")
def update_profile(payload: ProfileUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.email is not None:
        user.email = str(payload.email)
    db.commit()
    db.refresh(user)
    return user


@router.post("/password/change", summary="Сменить пароль")
def change_password(
    payload: PasswordChangeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Текущий пароль указан неверно")
    try:
        validate_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"ok": True, "message": "Пароль изменён"}


@router.post("/staff/phone-login", response_model=TokenOut, summary="Вход сотрудника по подтверждённому номеру")
def staff_phone_login(payload: PhoneLoginIn, db: Session = Depends(get_db)):
    """Единый вход для приложения: продавец и администратор входят тем же способом."""
    phone = phone_from_token(payload.phone_token)
    user = _user_by_phone(db, phone)
    if not user or user.role not in (ROLE_ADMIN, "seller"):
        raise HTTPException(status_code=403, detail="Нет доступа к рабочему интерфейсу")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован")
    return _issue(user)
