#!/usr/bin/env python3
"""Дымовой тест развёрнутого стенда (staging, демо, production).

Проверяет, что приложение поднялось, витрина и демо-магазин открываются,
демо-владелец может войти, ключевые API отвечают, а панель платформы доступна.

Примеры:
    python scripts/smoke.py --base-url http://127.0.0.1:8000 --demo --full
    python scripts/smoke.py --base-url https://staging.example.by \
        --host odezhda.staging.example.by
    python scripts/smoke.py --base-url https://torg.alwaysdata.net --demo --full

Скрипт использует только стандартную библиотеку Python и возвращает код 1,
если хотя бы одна проверка не прошла. Секреты можно передать переменными
окружения DEMO_ADMIN_PHONE / DEMO_ADMIN_PASSWORD / PLATFORM_ADMIN_PHONE /
PLATFORM_ADMIN_PASSWORD, чтобы они не попали в историю команд.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


class Failure(RuntimeError):
    pass


def request(
    base_url: str,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict | None = None,
    timeout: float = 20,
    insecure: bool = False,
) -> tuple[int, dict[str, str], bytes]:
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", "Torgovlia-Smoke/1.0")
    req.add_header("Accept", "application/json, text/html;q=0.9, */*;q=0.8")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    context = ssl._create_unverified_context() if insecure else None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def json_body(raw: bytes) -> dict:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Failure("ответ не является JSON") from exc


def login(base_url: str, path: str, phone: str, password: str, headers: dict[str, str], args) -> str:
    status, _, raw = request(
        base_url,
        "POST",
        path,
        headers=headers,
        body={"phone": phone, "password": password},
        timeout=args.timeout,
        insecure=args.insecure,
    )
    if status != 200:
        raise Failure(f"вход {path} вернул {status}: {raw[:200]!r}")
    token = json_body(raw).get("access_token")
    if not token:
        raise Failure(f"вход {path} не вернул access_token")
    return token


class Runner:
    def __init__(self, args) -> None:
        self.args = args
        self.passed = 0
        self.failed: list[str] = []
        self.skipped = 0

    def check(self, name: str, method: str, path: str, *, headers=None, body=None,
              expect=(200,), validate=None, optional=False) -> bytes | None:
        started = time.monotonic()
        try:
            status, resp_headers, raw = request(
                self.args.base_url,
                method,
                path,
                headers=headers,
                body=body,
                timeout=self.args.timeout,
                insecure=self.args.insecure,
            )
            if status not in expect:
                if optional and status in (403, 404):
                    self.skipped += 1
                    print(f"SKIP  {name}: HTTP {status} (сервис не подключён)")
                    return None
                raise Failure(f"HTTP {status}, ожидали {expect}: {raw[:300]!r}")
            if validate is not None:
                validate(raw, resp_headers)
            self.passed += 1
            elapsed = (time.monotonic() - started) * 1000
            print(f"OK    {name} ({elapsed:.0f} мс)")
            return raw
        except Exception as exc:  # noqa: BLE001 — smoke должен собрать все ошибки
            self.failed.append(name)
            print(f"FAIL  {name}: {exc}")
            return None

    def summary(self) -> int:
        total = self.passed + len(self.failed)
        print()
        if self.failed:
            print(f"Провалено {len(self.failed)} из {total} проверок: {', '.join(self.failed)}")
            return 1
        extra = f", пропущено {self.skipped}" if self.skipped else ""
        print(f"Smoke пройден: {self.passed} проверок{extra}.")
        return 0


def make_validators(args, tenant_slug: str | None):
    def health(raw: bytes, headers):
        data = json_body(raw)
        if data.get("status") != "ok":
            raise Failure(f"health.status={data.get('status')!r}")

    def site(raw: bytes, headers):
        data = json_body(raw)
        tenant = data.get("tenant") or {}
        if tenant_slug:
            if not tenant:
                raise Failure("tenant пуст — заголовок или домен не сработал")
            if tenant.get("slug") != tenant_slug:
                raise Failure(f"получен tenant {tenant.get('slug')!r}, ожидали {tenant_slug!r}")
        settings = data.get("settings") or {}
        if not settings.get("brand_name"):
            raise Failure("в настройках нет brand_name")
        features = data.get("features") or {}
        for key in ("promo_codes", "gift_certificates", "subscriptions"):
            if key not in features:
                raise Failure(f"в features нет {key}")

    def pages(raw: bytes, headers):
        if not raw:
            raise Failure("пустой ответ страницы")

    def list_items(raw: bytes, headers):
        data = json_body(raw)
        if "items" not in data:
            raise Failure("в ответе нет items")

    def plain_ok(raw: bytes, headers):
        return None

    return {
        "health": health,
        "site": site,
        "pages": pages,
        "list": list_items,
        "ok": plain_ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Дымовой тест Torgovlia")
    parser.add_argument("--base-url", default=os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--tenant", default=os.getenv("SMOKE_TENANT", "odezhda"),
                        help="slug магазина для заголовка X-Tenant-Slug (демо-режим)")
    parser.add_argument("--demo", action="store_true",
                        help="отправлять X-Tenant-Slug (нужен DEMO_MODE=true)")
    parser.add_argument("--host", default="", help="переопределить заголовок Host для проверки поддомена")
    parser.add_argument("--admin-phone", default=os.getenv("DEMO_ADMIN_PHONE", "+375291112288"))
    parser.add_argument("--admin-password", default=os.getenv("DEMO_ADMIN_PASSWORD", "ChangeMe123!"))
    parser.add_argument("--platform-phone", default=os.getenv("PLATFORM_ADMIN_PHONE", "+375291110000"))
    parser.add_argument("--platform-password", default=os.getenv("PLATFORM_ADMIN_PASSWORD", "ChangeMe123!"))
    parser.add_argument("--full", action="store_true", help="проверять платные сервисы (сертификаты, подписки, задачи)")
    parser.add_argument("--no-platform", action="store_true", help="не проверять панель платформы")
    parser.add_argument("--timeout", type=float, default=25)
    parser.add_argument("--insecure", action="store_true", help="не проверять TLS-сертификат")
    args = parser.parse_args()

    runner = Runner(args)
    if args.demo:
        tenant_slug = args.tenant
    elif args.host:
        tenant_slug = args.host.split(".", 1)[0]
    else:
        tenant_slug = None
    store_headers: dict[str, str] = {}
    if args.demo:
        store_headers["X-Tenant-Slug"] = args.tenant
    if args.host:
        store_headers["Host"] = args.host
    validators = make_validators(args, tenant_slug)

    runner.check("health", "GET", "/api/health", validate=validators["health"])
    runner.check("storefront /", "GET", "/", validate=validators["pages"])
    runner.check("signup wizard /new", "GET", "/new", validate=validators["pages"])
    if args.demo or args.host:
        runner.check(
            f"demo storefront /shop/{args.tenant}",
            "GET",
            f"/shop/{args.tenant}",
            validate=validators["pages"],
        )
    runner.check("site api", "GET", "/api/site", headers=store_headers, validate=validators["site"])

    try:
        token = login(args.base_url, "/api/auth/login", args.admin_phone, args.admin_password,
                      store_headers, args)
    except Failure as exc:
        runner.failed.append("store login")
        print(f"FAIL  store login: {exc}")
        token = None

    if token:
        auth = {"Authorization": f"Bearer {token}", **store_headers}
        admin_checks = [
            ("admin stats", "/api/admin/stats"),
            ("admin products", "/api/admin/products"),
            ("admin orders", "/api/admin/orders"),
            ("admin services", "/api/admin/services"),
            ("admin settings", "/api/admin/settings"),
        ]
        for name, path in admin_checks:
            runner.check(name, "GET", path, headers=auth, validate=validators["ok"])
        if args.full:
            runner.check("certificates", "GET", "/api/admin/certificates", headers=auth,
                         validate=validators["ok"], optional=True)
            runner.check("subscriptions", "GET", "/api/admin/subscriptions", headers=auth,
                         validate=validators["ok"], optional=True)
            runner.check("staff tasks", "GET", "/api/admin/tasks", headers=auth,
                         validate=validators["ok"], optional=True)
            runner.check("crm", "GET", "/api/admin/crm", headers=auth,
                         validate=validators["ok"], optional=True)
            runner.check("audit", "GET", "/api/admin/audit", headers=auth,
                         validate=validators["ok"])
        runner.check("admin csv export", "GET", "/api/admin/orders/export.csv", headers=auth,
                     validate=validators["pages"])

    if not args.no_platform:
        try:
            platform_token = login(
                args.base_url, "/api/platform/auth/login", args.platform_phone,
                args.platform_password, {}, args
            )
        except Failure as exc:
            runner.failed.append("platform login")
            print(f"FAIL  platform login: {exc}")
            platform_token = None
        if platform_token:
            pauth = {"Authorization": f"Bearer {platform_token}"}
            runner.check("platform stats", "GET", "/api/platform/stats", headers=pauth,
                         validate=validators["ok"])
            runner.check("platform tenants", "GET", "/api/platform/tenants", headers=pauth,
                         validate=validators["list"])

    return runner.summary()


if __name__ == "__main__":
    sys.exit(main())
