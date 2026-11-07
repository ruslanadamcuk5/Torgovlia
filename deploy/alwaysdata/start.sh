#!/usr/bin/env bash
# Запуск платформы Torgovlia на alwaysdata (тип сайта «User program»).
# alwaysdata передаёт адрес для прослушивания в IP и порт в PORT.
#
# При первом запуске (или после изменения requirements) скрипт сам создаёт
# виртуальное окружение и ставит зависимости. Это резервный путь: deploy.py
# старается подготовить окружение заранее по SSH.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT/backend"

mkdir -p data media/uploads

VENV="$ROOT/backend/.venv"
REQ="$ROOT/backend/requirements-deploy.txt"
if [ ! -f "$REQ" ]; then
  REQ="$ROOT/backend/requirements.txt"
fi
MARKER="$VENV/.requirements.sha256"

needs_install=1
if [ -x "$VENV/bin/uvicorn" ] && [ -f "$MARKER" ]; then
  current="$(sha256sum "$REQ" | awk '{print $1}')"
  if [ "$(cat "$MARKER" 2>/dev/null || true)" = "$current" ]; then
    needs_install=0
  fi
fi

if [ "$needs_install" = "1" ]; then
  echo "Torgovlia: preparing Python environment…"
  # На alwaysdata python — это обёртка нужной версии; python3 использовать нельзя.
  if [ ! -x "$VENV/bin/python" ]; then
    python -m venv "$VENV"
  fi
  "$VENV/bin/python" -m pip install --no-cache-dir --upgrade pip
  "$VENV/bin/python" -m pip install --no-cache-dir -r "$REQ"
  sha256sum "$REQ" | awk '{print $1}' > "$MARKER"
fi

echo "Torgovlia: applying database migrations…"
"$VENV/bin/python" -m alembic upgrade head

exec "$VENV/bin/uvicorn" app.main:app \
  --host "${IP:-::}" \
  --port "${PORT:-8100}" \
  --proxy-headers \
  --forwarded-allow-ips="*"
