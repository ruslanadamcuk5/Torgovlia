#!/usr/bin/env bash
# Ежедневный бэкап PostgreSQL и загруженных изображений (docker compose).
# Установка в cron:
#   15 3 * * * /opt/rybnaya-lavka/deploy/backup.sh >> /var/log/rybnaya-backup.log 2>&1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Не найден $ROOT/.env" >&2
  exit 1
fi

# shellcheck disable=SC1091
set -a
source .env
set +a

DIR="${BACKUP_DIR:-$ROOT/backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DIR"

docker compose exec -T db pg_dump -U "${POSTGRES_USER:-rybnaya}" "${POSTGRES_DB:-rybnaya}" \
  | gzip -9 > "$DIR/db-$STAMP.sql.gz"

docker compose exec -T app tar cf - -C /app/backend media \
  | gzip -9 > "$DIR/media-$STAMP.tar.gz"

# Оставляем 14 последних копий каждого типа.
find "$DIR" -name 'db-*.sql.gz' -type f -printf '%T@ %p\n' \
  | sort -nr | tail -n +15 | cut -d' ' -f2- | xargs -r rm -f
find "$DIR" -name 'media-*.tar.gz' -type f -printf '%T@ %p\n' \
  | sort -nr | tail -n +15 | cut -d' ' -f2- | xargs -r rm -f

echo "Бэкап готов: $DIR/db-$STAMP.sql.gz, $DIR/media-$STAMP.tar.gz"

# ВАЖНО: храните копии вне сервера (S3, Яндекс Диск, другой сервер).
# Бэкап на том же диске не защищает от потери сервера.
