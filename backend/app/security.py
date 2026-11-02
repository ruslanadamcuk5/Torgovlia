import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.config import settings


ALGORITHM = "HS256"


# ─────────────────────────── Телефоны ───────────────────────────

def normalize_phone(raw: str) -> str:
    """Приводит номер Республики Беларусь к формату +375XXXXXXXXX."""
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        raise ValueError("Укажите номер телефона")
    if digits.startswith("375") and len(digits) == 12:
        national = digits[3:]
    elif digits.startswith("80") and len(digits) == 11:
        national = digits[2:]
    elif len(digits) == 10 and digits.startswith("0"):
        national = digits[1:]
    elif len(digits) == 9:
        national = digits
    else:
        raise ValueError("Некорректный номер. Пример: +375 29 123-45-67")

    if len(national) != 9 or not national.startswith(("1", "2", "3", "4", "5", "6", "7", "8", "9")):
        raise ValueError("Некорректный номер. Пример: +375 29 123-45-67")
    return f"+375{national}"


def format_phone(phone: str) -> str:
    try:
        p = normalize_phone(phone)
    except ValueError:
        return phone
    return f"+375 ({p[4:6]}) {p[6:9]}-{p[9:11]}-{p[11:13]}"


# ─────────────────────────── Пароли ───────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def validate_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Пароль должен содержать минимум 8 символов")
    if len(password) > 128:
        raise ValueError("Пароль слишком длинный")
    if not re.search(r"[A-Za-zА-Яа-я]", password) or not re.search(r"\d", password):
        raise ValueError("Пароль должен содержать буквы и цифры")
    return password


# ─────────────────────────── JWT ───────────────────────────

def _encode(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_access_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return _encode(payload)


def create_phone_token(phone: str, purpose: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": phone,
        "purpose": purpose,
        "type": "phone",
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=settings.phone_token_minutes),
    }
    return _encode(payload)


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ─────────────────────────── SMS-коды ───────────────────────────

def generate_sms_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_sms_code(code: str, verification_id: str) -> str:
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        f"{verification_id}:{code}".encode("utf-8"),
        sha256,
    ).hexdigest()


def check_sms_code(code: str, verification_id: str, code_hash: str) -> bool:
    return hmac.compare_digest(hash_sms_code(code, verification_id), code_hash)
