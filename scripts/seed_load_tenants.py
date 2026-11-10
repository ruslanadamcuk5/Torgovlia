#!/usr/bin/env python3
"""Наполнение стенда арендаторами для нагрузочного теста (задача 10.1).

Создаёт N магазинов с префиксом (`load000`, `load001`, …), включёнными
сервисами и демо-каталогом по категории. Магазины помечаются `is_demo`,
поэтому не попадают в очередь провижининга и не создают задач деплоя.

Запуск из корня репозитория:
    DATABASE_URL=sqlite:////tmp/opencode/load.db \
        python3 scripts/seed_load_tenants.py --count 100

Скрипт идемпотентен: уже существующие slug пропускаются.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT / "backend")
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal, init_db  # noqa: E402
from app.models import Tenant  # noqa: E402
from app.platform.catalog import PLAN_BY_CODE  # noqa: E402
from app.platform.provisioning import CATEGORY_PRESETS, create_tenant  # noqa: E402
from app.platform.sync import sync_catalog  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Создать арендаторов для нагрузочного теста")
    parser.add_argument("--count", type=int, default=100, help="Сколько магазинов создать")
    parser.add_argument("--prefix", default="load", help="Префикс slug")
    parser.add_argument("--plan", default="business", choices=sorted(PLAN_BY_CODE))
    parser.add_argument("--start", type=int, default=0, help="Первый номер")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    sync_catalog(db)
    created = skipped = 0
    try:
        presets = [preset.code for preset in CATEGORY_PRESETS]
        for index in range(args.start, args.start + args.count):
            slug = f"{args.prefix}{index:03d}"
            if db.scalar(select(Tenant.id).where(Tenant.slug == slug)):
                skipped += 1
                continue
            preset = presets[index % len(presets)]
            tenant, _ = create_tenant(
                db,
                slug=slug,
                name=f"Нагрузочный магазин {index:03d}",
                plan_code=args.plan,
                category_preset=preset,
                is_demo=True,
                actor="loadtest-seed",
                audit_action="tenant.loadtest_seed",
            )
            # Публичная витрина работает и в onboarding, но active ближе к проду.
            tenant.status = "active"
            db.commit()
            created += 1
            if not args.quiet and (created % 10 == 0 or created == 1):
                print(f"  создано {created}/{args.count}: {slug} ({preset})", flush=True)
    finally:
        db.close()

    print(f"Готово: создано {created}, пропущено {skipped}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
