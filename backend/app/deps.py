from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    PLATFORM_OWNER,
    PLATFORM_ROLES,
    ROLE_ADMIN,
    ROLE_SELLER,
    PlatformUser,
    User,
)
from app.security import decode_token, normalize_phone
from app.tenancy import current_tenant_id


bearer = HTTPBearer(auto_error=False)


def _payload(credentials: HTTPAuthorizationCredentials | None) -> dict | None:
    if not credentials or not credentials.credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        return None
    return payload


def _resolve(credentials: HTTPAuthorizationCredentials | None, db: Session) -> User | None:
    payload = _payload(credentials)
    if not payload or payload.get("scope", "tenant") != "tenant":
        return None
    try:
        user_id = int(payload.get("sub", "0"))
    except (TypeError, ValueError):
        return None
    user = db.get(User, user_id)
    if not user or not user.is_active:
        return None
    tenant_id = current_tenant_id()
    if tenant_id is not None and user.tenant_id != tenant_id:
        # Токен магазина A не действует на витрине магазина B.
        return None
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User | None:
    return _resolve(credentials, db)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    user = _resolve(credentials, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != ROLE_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
    return user


def require_staff(user: User = Depends(get_current_user)) -> User:
    if user.role not in (ROLE_ADMIN, ROLE_SELLER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
    return user


# ─── Сотрудники платформы ───────────────────────────────────────────

def get_platform_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> PlatformUser:
    payload = _payload(credentials)
    if not payload or payload.get("scope") != "platform":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется вход в панель платформы")
    try:
        user_id = int(payload.get("sub", "0"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Некорректный токен")
    user = db.get(PlatformUser, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Доступ к платформе закрыт")
    if user.role not in PLATFORM_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
    return user


def require_platform(user: PlatformUser = Depends(get_platform_user)) -> PlatformUser:
    return user


def require_platform_owner(user: PlatformUser = Depends(get_platform_user)) -> PlatformUser:
    if user.role != PLATFORM_OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Действие доступно владельцу платформы")
    return user


def phone_from_token(token: str, expected_phone: str | None = None) -> str:
    payload = decode_token(token)
    if not payload or payload.get("type") != "phone":
        raise HTTPException(status_code=400, detail="Подтверждение номера недействительно. Запросите новый код.")
    phone = payload.get("sub")
    if not phone:
        raise HTTPException(status_code=400, detail="Подтверждение номера недействительно")
    phone = normalize_phone(phone)
    if expected_phone and normalize_phone(expected_phone) != phone:
        raise HTTPException(status_code=400, detail="Номер телефона не совпадает с подтверждённым")
    return phone


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "")[:64]
