"""Оповещения платформы: сводка проблем и отправка в Telegram.

Фонового воркера нет, поэтому сводка строится по запросу, а отправить её можно
из панели или внешним cron-вызовом. Токен бота и chat_id задаются только через
env и никогда не возвращаются в API.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.platform import ops


LEVEL_ERROR = "error"
LEVEL_WARNING = "warning"


def collect(db: Session) -> list[dict]:
    """Список проблем по всем магазинам, без дублей."""
    data = ops.overview(db, limit=500)
    alerts: list[dict] = []
    for item in data["items"]:
        if item["level"] == "ok":
            continue
        severity = LEVEL_ERROR if item["level"] == LEVEL_ERROR else LEVEL_WARNING
        for issue in item.get("issues") or []:
            alerts.append(
                {
                    "tenant_id": item["tenant_id"],
                    "slug": item["slug"],
                    "name": item["name"],
                    "severity": severity,
                    "message": issue,
                }
            )
    return alerts


def digest(db: Session) -> dict:
    alerts = collect(db)
    errors = sum(1 for item in alerts if item["severity"] == LEVEL_ERROR)
    warnings = len(alerts) - errors
    configured = bool(settings.telegram_bot_token and settings.telegram_chat_id)

    if alerts:
        lines = [
            f"Torgovlia: {len(alerts)} замечаний",
            f"Ошибки: {errors} · Предупреждения: {warnings}",
            "",
        ]
        for item in alerts[:40]:
            mark = "🔴" if item["severity"] == LEVEL_ERROR else "🟡"
            lines.append(f"{mark} {item['name']} /{item['slug']}: {item['message']}")
        if len(alerts) > 40:
            lines.append(f"…и ещё {len(alerts) - 40}")
        text = "\n".join(lines)
    else:
        text = "Torgovlia: все сайты в порядке, замечаний нет."

    return {
        "generated_at": datetime.now(timezone.utc),
        "total": len(alerts),
        "errors": errors,
        "warnings": warnings,
        "telegram_configured": configured,
        "alerts": alerts,
        "text": text[:3800],
    }


def send_telegram(text: str) -> None:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise RuntimeError("Telegram не настроен: TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID")

    body = urllib.parse.urlencode(
        {
            "chat_id": settings.telegram_chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
        data=body,
        method="POST",
    )
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"Telegram API: HTTP {exc.code} {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Telegram API недоступен: {exc.reason}") from exc

    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API: {str(payload)[:300]}")
