"""TOTP для двухфакторного входа сотрудников платформы.

Реализация без внешних зависимостей: RFC 6238, SHA-1, 30 секунд, 6 цифр.
Секрет хранится в БД в base32; резервные коды — только в виде SHA-256.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
import urllib.parse

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


DIGITS = 6
PERIOD = 30
WINDOW = 1
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def provisioning_uri(secret: str, account: str, issuer: str = "Torgovlia") -> str:
    label = urllib.parse.quote(f"{issuer}:{account}")
    params = urllib.parse.urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": DIGITS,
            "period": PERIOD,
        }
    )
    return f"otpauth://totp/{label}?{params}"


def _normalize(code: str) -> str:
    return "".join(ch for ch in code if ch.isdigit())


def _hotp(secret: str, counter: int) -> str:
    padding = "=" * (-len(secret) % 8)
    key = base64.b32decode(secret + padding, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10**DIGITS)).zfill(DIGITS)


def current_code(secret: str, at: float | None = None) -> str:
    return _hotp(secret, int((at or time.time()) // PERIOD))


def verify(secret: str | None, code: str, at: float | None = None) -> bool:
    if not secret:
        return False
    value = _normalize(code)
    if len(value) != DIGITS:
        return False
    counter = int((at or time.time()) // PERIOD)
    for shift in range(-WINDOW, WINDOW + 1):
        if hmac.compare_digest(_hotp(secret, counter + shift), value):
            return True
    return False


def generate_recovery_codes(count: int = 8) -> list[str]:
    codes = []
    for _ in range(count):
        raw = "".join(secrets.choice(ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


def hash_recovery_code(code: str) -> str:
    normalized = "".join(ch for ch in code.upper() if ch.isalnum())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
