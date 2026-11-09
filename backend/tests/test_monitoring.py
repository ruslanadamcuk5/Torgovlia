"""Мониторинг и алерты: проверка реального сбоя (задача 10.5).

Тесты не подменяют сетевой вызов: недоступный порт и локальный HTTP-сервер —
это настоящие соединения. Так проверяется вся цепочка «площадка → проверка →
сводка → алерт», а не только формирование ответа API.
"""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.db import SessionLocal
from app.models import Tenant, UptimeCheck
from app.platform import alerts, ops, uptime


def _closed_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _tenant(url: str, slug: str = "probe-monitor") -> Tenant:
    return Tenant(
        id=900_001,
        slug=slug,
        name="Магазин мониторинга",
        status="active",
        deploy_status="deployed",
        deploy_url=url,
    )


def test_probe_records_real_connection_failure():
    url = f"http://127.0.0.1:{_closed_port()}/api/site"
    check = uptime.probe_tenant(_tenant(url), timeout=2)
    assert check is not None
    assert check.ok is False
    assert check.status_code is None
    assert check.error


def test_probe_accepts_live_storefront_and_rejects_foreign_slug():
    class Handler(BaseHTTPRequestHandler):
        slug = "probe-monitor"

        def do_GET(self):  # noqa: N802 — имя метода HTTP-сервера
            body = json.dumps({"tenant": {"slug": self.slug}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # noqa: D401 — тишина в выводе тестов
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/api/site"
        healthy = uptime.probe_tenant(_tenant(url), timeout=3)
        assert healthy is not None and healthy.ok is True

        Handler.slug = "another-store"
        foreign = uptime.probe_tenant(_tenant(url), timeout=3)
        assert foreign is not None
        assert foreign.ok is False
        assert "витрину" in foreign.error
    finally:
        server.shutdown()
        server.server_close()
        Handler.slug = "probe-monitor"


def test_real_failure_becomes_alert(client):
    """Недоступный магазин попадает в overview как error и в сводку алертов."""
    slug = "monitor-failure-test"
    url = f"http://127.0.0.1:{_closed_port()}/api/site"
    with SessionLocal() as db:
        existing = db.query(Tenant).filter(Tenant.slug == slug).one_or_none()
        if existing:
            db.delete(existing)
            db.commit()
        tenant = Tenant(
            slug=slug,
            name="Недоступный магазин",
            status="active",
            plan_code="start",
            deploy_status="deployed",
            deploy_url=url,
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

    try:
        with SessionLocal() as db:
            result = uptime.run_checks(db, [tenant])
            assert result["checked"] == 1
            assert result["failed"] == 1

            overview = ops.overview(db)
            item = next(row for row in overview["items"] if row["slug"] == slug)
            assert item["level"] == "error"
            assert "Сайт не отвечает" in item["issues"]

            digest = alerts.digest(db)
            messages = [row["message"] for row in digest["alerts"] if row["slug"] == slug]
            assert "Сайт не отвечает" in messages
            assert digest["errors"] >= 1
    finally:
        with SessionLocal() as db:
            db.query(UptimeCheck).filter(UptimeCheck.tenant_id == tenant.id).delete()
            stored = db.query(Tenant).filter(Tenant.slug == slug).one_or_none()
            if stored:
                db.delete(stored)
            db.commit()


def test_cron_endpoint_requires_configured_token(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "cron_token", "")
    assert client.post("/api/platform/ops/cron").status_code == 503

    monkeypatch.setattr(settings, "cron_token", "test-cron-secret")
    assert client.post("/api/platform/ops/cron").status_code == 403
    wrong = client.post(
        "/api/platform/ops/cron", headers={"X-Cron-Token": "wrong"}
    )
    assert wrong.status_code == 403
    # Заголовок с не-ASCII не должен ронять сравнение токенов.
    bad_encoding = client.post(
        "/api/platform/ops/cron", headers={"X-Cron-Token": "токен".encode("utf-8")}
    )
    assert bad_encoding.status_code == 403


def test_cron_endpoint_runs_checks_and_reports_digest(client, monkeypatch):
    from app.api import platform_ops
    from app.config import settings

    monkeypatch.setattr(settings, "cron_token", "test-cron-secret")
    monkeypatch.setattr(
        platform_ops.uptime,
        "run_checks",
        lambda db, tenants=None: {"checked": 2, "ok": 1, "failed": 1, "results": []},
    )
    monkeypatch.setattr(
        platform_ops.alerts,
        "digest",
        lambda db: {
            "total": 1,
            "errors": 1,
            "warnings": 0,
            "telegram_configured": False,
            "text": "Torgovlia: 1 замечание",
        },
    )

    response = client.post(
        "/api/platform/ops/cron",
        headers={"X-Cron-Token": "test-cron-secret"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["checked"] == 2
    assert data["failed"] == 1
    assert data["alerts"] == 1
    assert data["telegram_configured"] is False
    assert data["telegram_sent"] is False
