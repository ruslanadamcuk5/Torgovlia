"""Сброс пароля пользователя (в том числе администратора).

Запуск из папки backend:
    .venv/bin/python ../scripts/reset_password.py +375291112233 'НовыйПароль123'
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal, init_db  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password, normalize_phone, validate_password  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Сбросить пароль пользователя")
    parser.add_argument("phone", help="Телефон в формате +375XXXXXXXXX")
    parser.add_argument("password", help="Новый пароль (минимум 8 символов, буквы и цифры)")
    args = parser.parse_args()

    try:
        phone = normalize_phone(args.phone)
        validate_password(args.password)
    except ValueError as exc:
        print(f"Ошибка: {exc}")
        return 1

    init_db()
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.phone == phone))
        if not user:
            print(f"Пользователь {phone} не найден")
            return 2
        user.password_hash = hash_password(args.password)
        user.is_active = True
        user.is_phone_verified = True
        db.commit()
        print(f"Пароль обновлён: {phone} ({user.role})")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
