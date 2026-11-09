#!/usr/bin/env python3
"""Плановая проверка доступности магазинов и отправка алертов.

Вызывает `POST /api/platform/ops/cron` с токеном `CRON_TOKEN`. Сервер сам
проверяет все магазины, считает сводку и отправляет её в Telegram, если канал
настроен. Скрипт нужен, чтобы повесить вызов в cron/планировщик хостинга и
видеть результат в логе.

Примеры:
    CRON_TOKEN='...' python3 scripts/uptime_check.py \
        --base-url https://torg.alwaysdata.net

    # Ручной прогон: ненулевой код, если есть проблемы
    CRON_TOKEN='...' python3 scripts/uptime_check.py --fail-on-problem

Скрипт использует только стандартную библиотеку Python.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Плановая проверка доступности Torgovlia")
    parser.add_argument(
        "--base-url",
        default=os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000"),
        help="адрес платформы (по умолчанию PUBLIC_BASE_URL)",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("CRON_TOKEN", ""),
        help="токен планировщика (по умолчанию CRON_TOKEN)",
    )
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--insecure", action="store_true", help="не проверять TLS-сертификат")
    parser.add_argument(
        "--fail-on-problem",
        action="store_true",
        help="вернуть код 3, если есть недоступные сайты или замечания",
    )
    parser.add_argument("--json", action="store_true", help="напечатать сырой JSON")
    args = parser.parse_args()

    token = args.token.strip()
    if not token:
        print("ОШИБКА: не задан CRON_TOKEN", file=sys.stderr)
        return 2

    url = args.base_url.rstrip("/") + "/api/platform/ops/cron"
    request = urllib.request.Request(url, data=b"", method="POST")
    request.add_header("X-Cron-Token", token)
    request.add_header("Accept", "application/json")
    request.add_header("User-Agent", "Torgovlia-Cron/1.0")
    context = ssl._create_unverified_context() if args.insecure else None

    try:
        with urllib.request.urlopen(request, timeout=args.timeout, context=context) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        print(f"ОШИБКА: HTTP {exc.code}: {detail[:500]}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — cron должен записать любую ошибку
        print(f"ОШИБКА: {exc}", file=sys.stderr)
        return 1

    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        print(f"ОШИБКА: ответ не JSON: {raw[:300]!r}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(
            f"Проверено магазинов: {data.get('checked', 0)}, "
            f"доступно: {data.get('ok', 0)}, сбоев: {data.get('failed', 0)}"
        )
        print(
            f"Замечаний: {data.get('alerts', 0)} "
            f"(ошибок {data.get('errors', 0)}, предупреждений {data.get('warnings', 0)})"
        )
        if data.get("telegram_configured"):
            state = "отправлена" if data.get("telegram_sent") else "не отправлена"
            print(f"Сводка в Telegram: {state}")
            if data.get("telegram_error"):
                print(f"Ошибка Telegram: {data['telegram_error']}")
        else:
            print("Telegram не настроен — сводка только в панели платформы")
        text = data.get("text") or ""
        if text:
            print()
            print(text)

    if args.fail_on_problem and (data.get("failed") or data.get("alerts")):
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
