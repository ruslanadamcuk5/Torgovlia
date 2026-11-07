#!/usr/bin/env python3
"""Деплой Torgovlia на alwaysdata через официальный API, FTP и SSH.

Скрипт использует только стандартную библиотеку Python и системный ssh.
Что делает:

1. Проверяет аккаунт alwaysdata по API-токену.
2. Собирает frontend с адресом платформы и демо-витринами.
3. Создаёт FTP-пользователя и загружает backend, frontend/dist и start.sh.
4. Создаёт/обновляет сайт типа user_program и при необходимости ставит
   Python-зависимости по SSH (иначе start.sh сделает это при первом запросе).
5. Создаёт backend/.env при первом деплое, перезапускает сайт и проверяет
   /api/health.

Токен передаётся только через переменную окружения ALWAYSDATA_TOKEN или
параметр --token. Пароли и ключ деплоя сохраняются в .deploy/ (gitignored).
"""

from __future__ import annotations

import argparse
import base64
import ftplib
import io
import json
import os
import secrets
import shlex
import ssl
import string
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


API_ROOT = "https://api.alwaysdata.com/v1"
REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "frontend"
BACKEND = REPO / "backend"
STATE_DIR = REPO / ".deploy"
STATE_FILE = STATE_DIR / "alwaysdata.json"
KEY_FILE = STATE_DIR / "alwaysdata_ed25519"

DEFAULT_PROJECT = "torgovlia"
DEFAULT_SITE_NAME = "Torgovlia"
DEFAULT_PYTHON = "3.12"

EXCLUDED_DIRS = {
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "data",
    "tests",
    "node_modules",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3"}
SKIP_MEDIA = True


# ───────────────────────────── API ─────────────────────────────

class ApiError(RuntimeError):
    pass


class Alwaysdata:
    def __init__(self, token: str, account: str | None = None) -> None:
        self.token = token
        self.account = account

    def call(self, method: str, path: str, data: dict | None = None):  # noqa: ANN201
        credential = self.token
        if self.account:
            credential = f"{self.token} account={self.account}"
        encoded = base64.b64encode(f"{credential}:".encode()).decode()
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
        request = urllib.request.Request(f"{API_ROOT}{path}", data=body, method=method)
        request.add_header("Authorization", f"Basic {encoded}")
        request.add_header("Accept", "application/json")
        if body is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            raise ApiError(f"{method} {path} → HTTP {exc.code}: {raw[:800]}") from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"{method} {path} → {exc.reason}") from exc


def as_list(value) -> list:  # noqa: ANN001
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("results", "items", "data"):
            if isinstance(value.get(key), list):
                return value[key]
    return []


def find_account(api: Alwaysdata, wanted: str | None) -> dict:
    accounts = as_list(api.call("GET", "/account/"))
    if not accounts:
        raise SystemExit("Токен не дал доступа ни к одному аккаунту alwaysdata.")
    if wanted:
        for account in accounts:
            if account.get("name") == wanted:
                return account
        names = ", ".join(str(item.get("name")) for item in accounts)
        raise SystemExit(f"Аккаунт «{wanted}» не найден. Доступны: {names}")
    if len(accounts) == 1:
        return accounts[0]
    names = ", ".join(str(item.get("name")) for item in accounts)
    raise SystemExit(f"У токена несколько аккаунтов: {names}. Укажите --account.")


# ───────────────────────────── FTP ─────────────────────────────

class FtpUploader:
    def __init__(self, account: str, username: str, password: str) -> None:
        self.host = f"ftp-{account}.alwaysdata.net"
        self.username = username
        self.password = password
        self.ftp: ftplib.FTP_TLS | None = None
        self.uploaded = 0

    def __enter__(self) -> "FtpUploader":
        context = ssl.create_default_context()
        client = ftplib.FTP_TLS(context=context)
        client.connect(self.host, 21, timeout=90)
        client.login(self.username, self.password)
        client.prot_p()
        client.set_pasv(True)
        self.ftp = client
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        if self.ftp is not None:
            try:
                self.ftp.quit()
            except Exception:  # noqa: BLE001
                self.ftp.close()

    def _ftp(self) -> ftplib.FTP_TLS:
        if self.ftp is None:
            raise RuntimeError("FTP не подключён")
        return self.ftp

    def ensure_dir(self, remote_dir: str) -> None:
        if remote_dir in ("", ".", "/"):
            return
        current = ""
        for part in [item for item in remote_dir.split("/") if item]:
            current = f"{current}/{part}" if current else part
            try:
                self._ftp().mkd(current)
            except ftplib.error_perm as exc:
                message = str(exc)
                if not (message.startswith("550") or "exists" in message.lower()):
                    raise

    def exists(self, remote: str) -> bool:
        try:
            self._ftp().size(remote)
            return True
        except ftplib.error_perm:
            return False
        except ftplib.error_temp:
            return False

    def download_text(self, remote: str) -> str | None:
        chunks: list[bytes] = []
        try:
            self._ftp().retrbinary(f"RETR {remote}", chunks.append)
        except ftplib.error_perm:
            return None
        return b"".join(chunks).decode("utf-8", "replace")

    def upload_text(self, remote: str, text: str) -> None:
        data = text.encode("utf-8")
        stream = io.BytesIO(data)
        self.ensure_dir(str(Path(remote).parent).replace("\\", "/"))
        self._ftp().storbinary(f"STOR {remote}", stream)
        self.uploaded += 1

    def upload(self, local: Path, remote: str) -> None:
        self.ensure_dir(str(Path(remote).parent).replace("\\", "/"))
        with local.open("rb") as handle:
            self._ftp().storbinary(f"STOR {remote}", handle, blocksize=128 * 1024)
        self.uploaded += 1

    def chmod(self, remote: str, mode: str) -> None:
        try:
            self._ftp().sendcmd(f"SITE CHMOD {mode} {remote}")
        except ftplib.all_errors:
            pass


# ───────────────────────────── SSH ─────────────────────────────

def random_password(length: int = 28) -> str:
    alphabet = string.ascii_letters + string.digits + "_-"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def ensure_ssh_key() -> str:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not KEY_FILE.exists():
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-N", "", "-C", "torgovlia-deploy", "-f", str(KEY_FILE)],
            check=True,
            capture_output=True,
            text=True,
        )
        KEY_FILE.chmod(0o600)
    return KEY_FILE.with_suffix(KEY_FILE.suffix + ".pub").read_text().strip()


def install_authorized_key(ftp: FtpUploader, public_key: str) -> None:
    remote = ".ssh/authorized_keys"
    existing = ftp.download_text(remote) or ""
    if public_key not in existing:
        existing = (existing.rstrip() + "\n" + public_key + "\n").lstrip()
        ftp.upload_text(remote, existing)
    ftp.chmod(".ssh", "700")
    ftp.chmod(remote, "600")


def ssh_run(user: str, account: str, command: str, timeout: int = 1800) -> subprocess.CompletedProcess:
    host = f"{user}@ssh-{account}.alwaysdata.net"
    return subprocess.run(
        [
            "ssh",
            "-i",
            str(KEY_FILE),
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "ConnectTimeout=25",
            host,
            command,
        ],
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def choose_ssh_user(api: Alwaysdata, account: str) -> str | None:
    users = as_list(api.call("GET", "/ssh/"))
    for user in users:
        if user.get("name") == account:
            return account
    deploy_name = f"{account}_deploy"
    for user in users:
        if user.get("name") == deploy_name:
            return deploy_name
    try:
        api.call(
            "POST",
            "/ssh/",
            {
                "name": deploy_name,
                "password": random_password(),
                "home_directory": "/",
                "shell": "BASH",
                "can_use_password": True,
                "annotation": "Torgovlia deploy",
            },
        )
        return deploy_name
    except ApiError as exc:
        print(f"! Не удалось создать SSH-пользователя: {exc}")
        return None


# ───────────────────────────── Сборка ─────────────────────────────

def build_frontend(domain: str, extra_addresses: list[str]) -> None:
    hosts = [domain, *extra_addresses]
    env = os.environ.copy()
    env["VITE_API_BASE_URL"] = "/api"
    env["VITE_PLATFORM_HOSTS"] = ",".join(hosts)
    env["VITE_DEMO_STOREFRONTS"] = "1"
    env["NODE_OPTIONS"] = "--max-old-space-size=1200"
    if not (FRONTEND / "node_modules").exists():
        print("→ npm ci")
        subprocess.run(["npm", "ci"], cwd=FRONTEND, check=True)
    print(f"→ npm run build (platform hosts: {env['VITE_PLATFORM_HOSTS']})")
    subprocess.run(["npm", "run", "build"], cwd=FRONTEND, env=env, check=True)


def deploy_requirements() -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    source = BACKEND / "requirements.txt"
    lines = [
        line
        for line in source.read_text(encoding="utf-8").splitlines()
        if not line.strip().lower().startswith("psycopg")
    ]
    target = STATE_DIR / "requirements-deploy.txt"
    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return target


def collect_files(extra_requirements: Path) -> list[tuple[Path, str]]:
    items: list[tuple[Path, str]] = []

    for path in sorted(BACKEND.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(REPO)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if SKIP_MEDIA and "media" in relative.parts:
            continue
        if path.name == ".env" or path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        items.append((path, relative.as_posix()))

    for path in sorted((FRONTEND / "dist").rglob("*")):
        if path.is_file():
            items.append((path, path.relative_to(REPO).as_posix()))

    items.append((REPO / "deploy" / "alwaysdata" / "start.sh", "start.sh"))
    items.append((extra_requirements, "backend/requirements-deploy.txt"))
    return items


# ───────────────────────────── .env ─────────────────────────────

def env_content(args: argparse.Namespace, domain: str) -> str:
    return "\n".join(
        [
            "ENVIRONMENT=production",
            "DEBUG=false",
            f"SECRET_KEY={secrets.token_urlsafe(48)}",
            f"PUBLIC_BASE_URL=https://{domain}",
            f"CORS_ORIGINS=https://{domain},http://{domain}",
            "",
            f"PLATFORM_HOST={domain}",
            f"PLATFORM_BASE_DOMAIN={domain}",
            "DEFAULT_TENANT_SLUG=rybnaya",
            "TENANT_HEADER_ENABLED=true",
            "DEMO_MODE=true",
            "",
            "DATABASE_URL=sqlite:///./data/torgovlia.db",
            "MEDIA_ROOT=media",
            "UPLOAD_MAX_MB=8",
            "",
            "SMS_PROVIDER=console",
            "SMS_EXPOSE_CODE=true",
            "",
            "ADMIN_PHONE=+375291112233",
            f"ADMIN_PASSWORD={args.admin_password}",
            "ADMIN_NAME=Владелец магазина",
            "",
            "PLATFORM_ADMIN_PHONE=+375291110000",
            f"PLATFORM_ADMIN_PASSWORD={args.platform_password}",
            "PLATFORM_ADMIN_NAME=Владелец платформы",
            "",
            "SEED_DEMO=true",
            "SEED_CATALOG=true",
            "",
        ]
    )


# ───────────────────────────── Сайт ─────────────────────────────

def ensure_site(
    api: Alwaysdata,
    args: argparse.Namespace,
    account: str,
    domain: str,
    extra_addresses: list[str],
) -> dict:
    sites = as_list(api.call("GET", "/site/"))
    addresses = [domain, *extra_addresses]

    def site_hosts(site: dict) -> set[str]:
        raw = [*(site.get("addresses") or []), site.get("address") or ""]
        hosts: set[str] = set()
        for item in raw:
            host = str(item).split("/")[0].strip().lower()
            if host:
                hosts.add(host)
        return hosts

    wanted = {domain.lower(), *(address.lower() for address in extra_addresses)}
    existing = next((site for site in sites if site_hosts(site) & wanted), None)
    if existing is None and len(sites) == 1 and domain.lower().endswith(".alwaysdata.net"):
        # A fresh alwaysdata account ships with a default PHP site on the
        # account address; reuse it instead of failing to create a duplicate.
        existing = sites[0]
        print(f"! Адрес {domain} не найден, переиспользую единственный сайт #{existing.get('id')}")
    payload = {
        "name": args.site_name,
        "addresses": addresses,
        "type": "user_program",
        "path": f"/{args.project}",
        "command": f"bash /home/{account}/{args.project}/start.sh",
        "working_directory": f"/{args.project}",
        "environment": f"PYTHON_VERSION={args.python_version} PYTHONUNBUFFERED=1",
        "ssl_force": False,
        "max_idle_time": 1800,
    }
    if existing:
        print(f"→ Обновляю сайт #{existing['id']} ({domain})")
        result = api.call("PATCH", f"/site/{existing['id']}/", payload)
        if isinstance(result, dict) and result.get("id"):
            return result
        return {"id": existing["id"]}
    print(f"→ Создаю сайт {domain} (user_program)")
    return api.call("POST", "/site/", payload)


def restart_site(api: Alwaysdata, site_id: int) -> None:
    try:
        api.call("POST", f"/site/{site_id}/restart/")
        print("→ Сайт перезапущен")
    except ApiError as exc:
        print(f"! Перезапуск через API не удался: {exc}. Перезапустите сайт в панели.")


def verify(domain: str, wait_seconds: int) -> bool:
    if wait_seconds <= 0:
        return True
    context = ssl._create_unverified_context()  # noqa: SLF001
    url = f"https://{domain}/api/health"
    deadline = time.time() + wait_seconds
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "torgovlia-deploy"})
            with urllib.request.urlopen(request, timeout=15, context=context) as response:
                payload = response.read().decode("utf-8", "replace")
                if response.status == 200:
                    print(f"✓ {url} → {payload[:200]}")
                    return True
        except Exception as exc:  # noqa: BLE001
            if attempt == 1 or attempt % 4 == 0:
                print(f"… ждём запуск ({attempt}): {exc}")
        time.sleep(5)
    print(f"! Сайт не ответил за {wait_seconds} с. Проверьте логи:")
    print(f"  /home/{domain.split('.')[0]}/admin/logs/sites/")
    return False


# ───────────────────────────── main ─────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Деплой Torgovlia на alwaysdata")
    parser.add_argument("--account", help="Имя аккаунта alwaysdata (если их несколько)")
    parser.add_argument(
        "--token",
        default=os.environ.get("ALWAYSDATA_TOKEN", ""),
        help="API-токен alwaysdata (по умолчанию ALWAYSDATA_TOKEN)",
    )
    parser.add_argument("--domain", help="Основной адрес сайта (по умолчанию <account>.alwaysdata.net)")
    parser.add_argument(
        "--extra-address",
        action="append",
        default=[],
        help="Дополнительный адрес сайта (можно несколько раз)",
    )
    parser.add_argument("--project", default=DEFAULT_PROJECT, help="Каталог проекта в аккаунте")
    parser.add_argument("--site-name", default=DEFAULT_SITE_NAME, help="Название сайта в панели")
    parser.add_argument("--python-version", default=DEFAULT_PYTHON, help="Версия Python на сайте")
    parser.add_argument("--admin-password", default="ChangeMe123!", help="Пароль владельца магазина")
    parser.add_argument(
        "--platform-password",
        default="ChangeMe123!",
        help="Пароль владельца платформы",
    )
    parser.add_argument("--env-file", help="Готовый backend/.env для загрузки")
    parser.add_argument("--force-env", action="store_true", help="Перезаписать backend/.env")
    parser.add_argument("--skip-build", action="store_true", help="Не собирать frontend")
    parser.add_argument("--skip-upload", action="store_true", help="Не загружать файлы")
    parser.add_argument("--skip-install", action="store_true", help="Не ставить зависимости по SSH")
    parser.add_argument("--skip-verify", action="store_true", help="Не ждать /api/health")
    parser.add_argument("--wait", type=int, default=150, help="Сколько секунд ждать запуск")
    parser.add_argument("--dry-run", action="store_true", help="Только показать план")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.token:
        print("Нужен API-токен alwaysdata: Profile → Tokens → Create.", file=sys.stderr)
        print("Передайте его в ALWAYSDATA_TOKEN или --token.", file=sys.stderr)
        return 2

    api = Alwaysdata(args.token)
    account_info = find_account(api, args.account)
    account = account_info["name"]
    api.account = account
    domain = (args.domain or f"{account}.alwaysdata.net").strip().lower()
    extra_addresses = [item.strip().lower() for item in args.extra_address if item.strip()]

    print(f"Аккаунт: {account}")
    print(f"Домен:   https://{domain}")
    print(f"Проект:  /home/{account}/{args.project}")

    if args.dry_run:
        print("Dry-run: сборка, загрузка и создание сайта пропущены.")
        return 0

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Python на аккаунте: версия из --python-version.
    try:
        api.call("PATCH", "/environment/python/", {"python_version": args.python_version})
        print(f"→ Python {args.python_version} включён для аккаунта")
    except ApiError as exc:
        print(f"! Не удалось переключить Python: {exc}")

    if not args.skip_build:
        build_frontend(domain, extra_addresses)

    # FTP-пользователь: пароль храним в .deploy/ для повторных деплоев.
    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}
    ftp_password = state.get("ftp_password") or random_password()
    ftp_username = f"{account}_deploy"
    ftp_users = as_list(api.call("GET", "/ftp/"))
    ftp_user = next((item for item in ftp_users if item.get("name") == ftp_username), None)
    if ftp_user:
        api.call("PATCH", f"/ftp/{ftp_user['id']}/", {"password": ftp_password})
    else:
        api.call(
            "POST",
            "/ftp/",
            {
                "name": ftp_username,
                "password": ftp_password,
                "path": "/",
                "annotation": "Torgovlia deploy",
            },
        )
        print(f"→ Создан FTP-пользователь {ftp_username}")

    ssh_user = choose_ssh_user(api, account)
    public_key = ensure_ssh_key()

    requirements = deploy_requirements()
    files = collect_files(requirements)
    total_bytes = sum(path.stat().st_size for path, _ in files)
    print(f"→ К загрузке: {len(files)} файлов, {total_bytes / 1024 / 1024:.1f} МБ")

    if args.skip_upload:
        print("Загрузка пропущена (--skip-upload).")
    else:
        with FtpUploader(account, ftp_username, ftp_password) as ftp:
            ftp.ensure_dir(f"{args.project}/backend/data")
            ftp.ensure_dir(f"{args.project}/backend/media/uploads")
            if ssh_user:
                try:
                    install_authorized_key(ftp, public_key)
                    print("→ SSH-ключ добавлен в authorized_keys")
                except Exception as exc:  # noqa: BLE001
                    print(f"! Не удалось добавить SSH-ключ: {exc}")

            if args.force_env or not ftp.exists(f"{args.project}/backend/.env"):
                if args.env_file:
                    content = Path(args.env_file).read_text(encoding="utf-8")
                else:
                    content = env_content(args, domain)
                ftp.upload_text(f"{args.project}/backend/.env", content)
                print("→ Создан backend/.env")
            else:
                print("→ backend/.env уже есть, не трогаю (--force-env для перезаписи)")

            for index, (local, remote) in enumerate(files, start=1):
                ftp.upload(local, f"{args.project}/{remote}")
                if index % 25 == 0 or index == len(files):
                    print(f"  загружено {index}/{len(files)}")

    # Зависимости по SSH — чтобы первый запрос не ждал pip.
    installed = False
    if ssh_user and not args.skip_install:
        print(f"→ SSH: ставлю зависимости ({ssh_user}@ssh-{account}.alwaysdata.net)")
        command = (
            f"cd /home/{account}/{shlex.quote(args.project)} && "
            "mkdir -p backend/data backend/media/uploads && "
            f"PYTHON_VERSION={shlex.quote(args.python_version)} python -m venv backend/.venv && "
            "backend/.venv/bin/python -m pip install --no-cache-dir --upgrade pip && "
            "backend/.venv/bin/python -m pip install --no-cache-dir -r backend/requirements-deploy.txt && "
            "sha256sum backend/requirements-deploy.txt | awk '{print $1}' > backend/.venv/.requirements.sha256"
        )
        result = ssh_run(ssh_user, account, command, timeout=2400)
        if result.returncode == 0:
            print("✓ Зависимости установлены")
            installed = True
        else:
            print("! SSH-установка не удалась, start.sh попробует сам при первом запросе")
            if result.stderr.strip():
                print(result.stderr.strip()[-1500:])
    elif not ssh_user:
        print("! SSH-пользователь недоступен — start.sh поставит зависимости при первом запросе")

    site = ensure_site(api, args, account, domain, extra_addresses)
    site_id = site.get("id")
    if site_id:
        restart_site(api, int(site_id))

    state.update(
        {
            "account": account,
            "domain": domain,
            "project": args.project,
            "site_id": site_id,
            "ftp_user": ftp_username,
            "ftp_password": ftp_password,
            "ssh_user": ssh_user,
            "dependencies_installed": installed,
            "deployed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    STATE_FILE.chmod(0o600)

    ok = verify(domain, 0 if args.skip_verify else args.wait)

    print("\n─── Готово ─────────────────────────────────────────────")
    print(f"Сайт платформы:  https://{domain}/start")
    print(f"Панель:          https://{domain}/platform/login")
    print(f"Витрина демо:    https://{domain}/shop/rybnaya")
    print(f"Ещё магазины:    https://{domain}/shop/flowers, https://{domain}/shop/meat, https://{domain}/shop/odezhda")
    print(f"API health:      https://{domain}/api/health")
    print("\nДоступы демо-стенда (смените перед реальным запуском):")
    print(f"  платформа: +375291110000 / {args.platform_password}")
    print(f"  магазин:   +375291112233 / {args.admin_password}")
    print("\nЛоги сайта: /home/{}/admin/logs/sites/".format(account))
    if not installed:
        print("Первый запрос может занять 1–2 минуты: ставятся Python-зависимости.")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
