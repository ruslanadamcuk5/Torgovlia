"""Очистка данных по срокам хранения (PD-аудит, задача 10.3).

По умолчанию только показывает, что будет удалено. Для удаления добавьте
`--apply`. Скрипт не трогает заказы и бухгалтерские документы: их обезличивают
вручную или отдельной процедурой после согласования сроков.

Запуск из папки backend:
    .venv/bin/python ../scripts/pd_cleanup.py
    .venv/bin/python ../scripts/pd_cleanup.py --apply

Cron (пример):
    30 3 * * * cd /home/torg/torgovlia/backend && .venv/bin/python ../scripts/pd_cleanup.py --apply >> /home/torg/pd-cleanup.log 2>&1
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import delete, func, select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    AuditLog,
    Cart,
    Order,
    PhoneVerification,
    PlatformEvent,
)


RULES = (
    ("SMS-коды", PhoneVerification, "created_at", 1),
    ("Брошенные корзины", Cart, "last_activity_at", 30),
    ("Обезличенная аналитика", PlatformEvent, "created_at", 90),
    ("Журнал действий", AuditLog, "created_at", 365),
)


def _cutoff(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _count(db, model, field: str, days: int) -> int:
    column = getattr(model, field)
    return int(db.scalar(select(func.count()).select_from(model).where(column < _cutoff(days))) or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Очистка персональных данных по срокам")
    parser.add_argument("--apply", action="store_true", help="удалить строки (без флага — только отчёт)")
    parser.add_argument("--keep-audit-days", type=int, default=365,
                        help="срок хранения журнала действий, по умолчанию 365 дней")
    args = parser.parse_args()

    print("Правила хранения:")
    for title, model, field, days in RULES:
        days_value = args.keep_audit_days if model is AuditLog else days
        print(f"  {title}: {days_value} дн. ({model.__tablename__}.{field})")
    # Заказы считаем отдельно: их нельзя удалять, только обезличивать.
    with SessionLocal() as db:
        orders_5y = int(
            db.scalar(
                select(func.count())
                .select_from(Order)
                .where(Order.created_at < _cutoff(365 * 5))
            )
            or 0
        )
        print(f"  Заказы старше 5 лет (только обезличивание): {orders_5y}")

        total = 0
        for title, model, field, days in RULES:
            days_value = args.keep_audit_days if model is AuditLog else days
            column = getattr(model, field)
            count = _count(db, model, field, days_value)
            total += count
            print(f"{title}: к удалению {count}")
            if args.apply and count:
                db.execute(delete(model).where(column < _cutoff(days_value)))
        if args.apply:
            db.commit()
            print(f"Удалено строк: {total}")
        else:
            print("Это отчёт без изменений. Для удаления запустите с --apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
