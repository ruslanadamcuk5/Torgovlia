#!/usr/bin/env bash
# Ежедневный бэкап базы, медиа и манифеста.
#
# Поддерживает SQLite (alwaysdata, staging, небольшой сервер) и PostgreSQL
# (docker compose или внешний сервер). Скрипт не требует root.
#
# Установка в cron (пример для alwaysdata; путь замените на свой):
#   15 3 * * * /home/torg/torgovlia/deploy/backup.sh >> /home/torg/backup.log 2>&1
#
# Переменные окружения:
#   DATABASE_URL      — берётся из .env, если файл есть; иначе из окружения.
#   BACKUP_DIR        — каталог копий (по умолчанию ./backups).
#   BACKUP_KEEP       — сколько копий каждого типа хранить (по умолчанию 14).
#   BACKUP_ENV_FILE   — явный путь к .env (удобно для staging).
#
# ВАЖНО: копии на том же диске не защищают от потери сервера. Настройте
# выгрузку каталога BACKUP_DIR во внешнее хранилище (S3, Яндекс Диск, другой
# сервер) и раз в месяц проверяйте восстановление: deploy/restore.sh --verify-only.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${BACKUP_ENV_FILE:-}"
if [[ -z "$ENV_FILE" ]]; then
  if [[ -f "$ROOT/.env" ]]; then
    ENV_FILE="$ROOT/.env"
  elif [[ -f "$ROOT/backend/.env" ]]; then
    ENV_FILE="$ROOT/backend/.env"
  fi
fi
if [[ -n "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
fi

DATABASE_URL="${DATABASE_URL:-sqlite:///./data/rybnaya.db}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
KEEP="${BACKUP_KEEP:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR" 2>/dev/null || true

DB_FILE=""
MEDIA_FILE=""
MANIFEST="$BACKUP_DIR/manifest-$STAMP.txt"

log() { printf '%s %s\n' "$(date '+%H:%M:%S')" "$*"; }
fail() { log "ОШИБКА: $*" >&2; exit 1; }

resolve_sqlite_path() {
  local url="$1" path
  path="${url#sqlite:///}"
  if [[ "$path" == "$url" ]]; then
    fail "DATABASE_URL должен начинаться с sqlite:/// или postgresql"
  fi
  if [[ "$path" != /* ]]; then
    path="$ROOT/backend/${path#./}"
  fi
  printf '%s' "$path"
}

backup_sqlite() {
  local src="$1" raw="$BACKUP_DIR/db-$STAMP.sqlite3"
  [[ -f "$src" ]] || fail "файл базы не найден: $src"
  command -v python3 >/dev/null || fail "нужен python3 для копирования SQLite"
  log "SQLite: копирую $src"
  python3 - "$src" "$raw" <<'PY'
import sqlite3
import sys

source, target = sys.argv[1], sys.argv[2]
src = sqlite3.connect(source)
dst = sqlite3.connect(target)
try:
    with dst:
        src.backup(dst)
finally:
    src.close()
    dst.close()
PY
  python3 - "$raw" <<'PY'
import sqlite3
import sys

conn = sqlite3.connect(sys.argv[1])
try:
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
finally:
    conn.close()
if result != "ok":
    raise SystemExit(f"SQLite integrity_check: {result}")
PY
  gzip -9 -c "$raw" > "$raw.gz"
  rm -f "$raw"
  DB_FILE="$raw.gz"
}

backup_postgres() {
  local raw="$BACKUP_DIR/db-$STAMP.sql.gz" url="${DATABASE_URL/postgresql+psycopg/postgresql}"
  if docker compose version >/dev/null 2>&1 && docker compose ps db >/dev/null 2>&1; then
    log "PostgreSQL: pg_dump через docker compose"
    docker compose exec -T db pg_dump -U "${POSTGRES_USER:-rybnaya}" "${POSTGRES_DB:-rybnaya}" \
      | gzip -9 > "$raw"
  else
    command -v pg_dump >/dev/null || fail "нужен pg_dump или запущенный сервис db в docker compose"
    log "PostgreSQL: pg_dump по DATABASE_URL"
    pg_dump --dbname="$url" --no-owner --no-privileges | gzip -9 > "$raw"
  fi
  [[ -s "$raw" ]] || fail "pg_dump вернул пустой файл"
  gzip -t "$raw" || fail "повреждённый gzip: $raw"
  DB_FILE="$raw"
}

backup_media() {
  local source="${MEDIA_ROOT:-$ROOT/backend/media}"
  if [[ "$source" != /* ]]; then
    source="$ROOT/backend/${source#./}"
  fi
  local raw="$BACKUP_DIR/media-$STAMP.tar.gz"
  if [[ -d "$source" ]] && find "$source" -type f -print -quit | grep -q .; then
    log "Медиа: архивирую $source"
    tar czf "$raw" -C "$(dirname "$source")" "$(basename "$source")"
  elif docker compose version >/dev/null 2>&1 && docker compose ps app >/dev/null 2>&1; then
    log "Медиа: архивирую том контейнера app"
    docker compose exec -T app tar czf - -C /app/backend media > "$raw"
  else
    log "Медиа: файлов нет, создаю пустой архив"
    tar czf "$raw" --files-from /dev/null
  fi
  gzip -t "$raw" || fail "повреждённый архив медиа: $raw"
  MEDIA_FILE="$raw"
}

if [[ "$DATABASE_URL" == sqlite:* ]]; then
  backup_sqlite "$(resolve_sqlite_path "$DATABASE_URL")"
elif [[ "$DATABASE_URL" == postgresql* ]]; then
  backup_postgres
else
  fail "неизвестный тип DATABASE_URL: ${DATABASE_URL%%:*}"
fi

backup_media

COMMIT="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
{
  echo "created_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "host=$(hostname)"
  echo "commit=$COMMIT"
  echo "database_url_type=${DATABASE_URL%%:*}"
  echo "env_file=${ENV_FILE:-<environment>}"
  echo "keep=$KEEP"
  echo "db=$(basename "$DB_FILE")"
  echo "media=$(basename "$MEDIA_FILE")"
} > "$MANIFEST"

# Контрольные суммы помогают заметить повреждение при выгрузке во внешнее хранилище.
(
  cd "$BACKUP_DIR"
  sha256sum "$(basename "$DB_FILE")" "$(basename "$MEDIA_FILE")" "$(basename "$MANIFEST")" \
    > "SHA256SUMS-$STAMP.txt"
)
chmod 600 "$BACKUP_DIR"/*"$STAMP"* 2>/dev/null || true

# Оставляем KEEP последних копий каждого типа.
for pattern in 'db-*' 'media-*' 'manifest-*' 'SHA256SUMS-*'; do
  find "$BACKUP_DIR" -maxdepth 1 -name "$pattern" -type f -printf '%T@ %p\n' \
    | sort -nr | tail -n +"$((KEEP + 1))" | cut -d' ' -f2- | xargs -r rm -f
done

log "Бэкап готов:"
log "  база:     $DB_FILE"
log "  медиа:    $MEDIA_FILE"
log "  манифест: $MANIFEST"
log "Проверка: deploy/restore.sh --verify-only --db '$DB_FILE' --media '$MEDIA_FILE'"
