from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ROLE_ADMIN, ROLE_SELLER, User
from app.security import decode_token, normalize_phone


bearer = HTTPBearer(auto_error=False)


def _resolve(credentials: HTTPAuthorizationCredentials | None, db: Session) -> User | None:
    if not credentials or not credentials.credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        return None
    try:
        user_id = int(payload.get("sub", "0"))
    except (TypeError, ValueError):
        return None
    user = db.get(User, user_id)
    if not user or not user.is_active:
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
