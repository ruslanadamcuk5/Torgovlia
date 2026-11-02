#!/usr/bin/env bash
# Запуск сайта «Рыбная лавка» на alwaysdata (тип сайта «User program»).
# alwaysdata передаёт адрес для прослушивания в IP и порт в PORT.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT/backend"

mkdir -p data media/uploads

exec .venv/bin/uvicorn app.main:app \
  --host "${IP:-::}" \
  --port "${PORT:-8100}" \
  --proxy-headers \
  --forwarded-allow-ips="*"
