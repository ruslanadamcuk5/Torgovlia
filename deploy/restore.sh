#!/usr/bin/env bash
# Восстановление из бэкапа и учебная проверка копии без изменения рабочей базы.
#
# Примеры:
#   # Только проверить, что копия читается (безопасно, можно на проде)
#   deploy/restore.sh --verify-only --db backups/db-20261109-031500.sqlite3.gz
#
#   # Восстановить базу и медиа (остановите приложение!)
#   deploy/restore.sh --db backups/db-...sqlite3.gz --media backups/media-....tar.gz --yes
#
#   # Восстановить PostgreSQL из дампа
#   deploy/restore.sh --db backups/db-...sql.gz --yes
#
# Скрипт всегда делает резервную копию текущей базы/медиа перед заменой.
# Для SQLite приложение должно быть остановлено: копирование поверх открытого
# файла может потерять последние транзакции.
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
  # Не source: значения с пробелами (имена, адреса) ломают shell. Читаем
  # только нужные ключи и не выполняем содержимое .env.
  env_get() {
    local key="$1" line
    line="$(grep -m1 "^${key}=" "$ENV_FILE" 2>/dev/null || true)"
    [[ -n "$line" ]] || return 1
    line="${line#*=}"
    line="${line%$'\r'}"
    if [[ ${#line} -ge 2 && "${line:0:1}" == '"' && "${line: -1}" == '"' ]]; then
      line="${line:1:${#line}-2}"
    elif [[ ${#line} -ge 2 && "${line:0:1}" == "'" && "${line: -1}" == "'" ]]; then
      line="${line:1:${#line}-2}"
    fi
    printf '%s' "$line"
  }
  DATABASE_URL="${DATABASE_URL:-$(env_get DATABASE_URL || true)}"
  MEDIA_ROOT="${MEDIA_ROOT:-$(env_get MEDIA_ROOT || true)}"
fi

DATABASE_URL="${DATABASE_URL:-sqlite:///./data/rybnaya.db}"
DB_BACKUP=""
MEDIA_BACKUP=""
VERIFY_ONLY=0
ASSUME_YES=0
STAMP="$(date +%Y%m%d-%H%M%S)"

usage() {
  sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

log() { printf '%s %s\n' "$(date '+%H:%M:%S')" "$*"; }
fail() { log "ОШИБКА: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db) DB_BACKUP="${2:-}"; shift 2 ;;
    --media) MEDIA_BACKUP="${2:-}"; shift 2 ;;
    --verify-only) VERIFY_ONLY=1; shift ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    --help|-h) usage 0 ;;
    *) fail "неизвестный аргумент: $1 (см. --help)" ;;
  esac
done

[[ -n "$DB_BACKUP" || -n "$MEDIA_BACKUP" ]] || usage 1
[[ -n "$DB_BACKUP" ]] && [[ -f "$DB_BACKUP" ]] || fail "файл базы не найден: ${DB_BACKUP:-<пусто>}"
if [[ -n "$MEDIA_BACKUP" ]]; then
  [[ -f "$MEDIA_BACKUP" ]] || fail "файл медиа не найден: $MEDIA_BACKUP"
fi

resolve_sqlite_path() {
  local url="$1" path
  path="${url#sqlite:///}"
  if [[ "$path" != /* ]]; then
    path="$ROOT/backend/${path#./}"
  fi
  printf '%s' "$path"
}

verify_sqlite() {
  local archive="$1" temp
  gzip -t "$archive" || fail "повреждённый gzip: $archive"
  temp="$(mktemp "${TMPDIR:-/tmp}/torgovlia-restore-XXXXXX.sqlite3")"
  gzip -dc "$archive" > "$temp"
  python3 - "$temp" <<'PY'
import sqlite3
import sys

conn = sqlite3.connect(sys.argv[1])
try:
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    tables = conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchone()[0]
    revision = None
    try:
        revision = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    except sqlite3.Error:
        pass
finally:
    conn.close()
if integrity != "ok":
    raise SystemExit(f"SQLite integrity_check: {integrity}")
if tables < 1:
    raise SystemExit("в копии нет таблиц")
print(f"SQLite ok: таблиц {tables}, Alembic {revision[0] if revision else 'нет'}")
PY
  rm -f "$temp"
}

verify_postgres() {
  local archive="$1" temp
  gzip -t "$archive" || fail "повреждённый gzip: $archive"
  temp="$(mktemp "${TMPDIR:-/tmp}/torgovlia-restore-XXXXXX.sql")"
  gzip -dc "$archive" > "$temp"
  [[ -s "$temp" ]] || fail "дамп пуст"
  local tables
  tables="$(grep -c '^CREATE TABLE' "$temp" || true)"
  [[ "$tables" -gt 0 ]] || fail "в дампе нет CREATE TABLE"
  echo "PostgreSQL dump ok: CREATE TABLE $tables"
  rm -f "$temp"
}

verify_media() {
  local archive="$1" count
  gzip -t "$archive" || fail "повреждённый gzip: $archive"
  count="$(tar tzf "$archive" | wc -l | tr -d ' ')"
  echo "Media archive ok: файлов $count"
}

verify() {
  local started elapsed
  started=$(date +%s)
  log "Проверяю копии (без изменения рабочей базы)"
  if [[ -n "$DB_BACKUP" ]]; then
    case "$DB_BACKUP" in
      *.sql.gz) verify_postgres "$DB_BACKUP" ;;
      *.sqlite3.gz|*.db.gz) verify_sqlite "$DB_BACKUP" ;;
      *) fail "неизвестное расширение базы: $DB_BACKUP (ожидается .sqlite3.gz или .sql.gz)" ;;
    esac
  fi
  [[ -n "$MEDIA_BACKUP" ]] && verify_media "$MEDIA_BACKUP"
  elapsed=$(( $(date +%s) - started ))
  log "Проверка пройдена за ${elapsed} с."
}

confirm() {
  [[ "$ASSUME_YES" == "1" ]] && return
  echo "Будут заменены рабочие данные. Приложение должно быть остановлено."
  read -r -p "Продолжить? Введите yes: " answer
  [[ "$answer" == "yes" ]] || fail "отменено"
}

restore_sqlite() {
  local target="$1"
  local safety="$target.pre-restore-$STAMP"
  if [[ -f "$target" ]]; then
    log "Сохраняю текущую базу: $safety"
    cp -p "$target" "$safety"
  fi
  mkdir -p "$(dirname "$target")"
  gzip -dc "$DB_BACKUP" > "$target.restore-$STAMP"
  chmod 600 "$target.restore-$STAMP"
  python3 - "$target.restore-$STAMP" <<'PY'
import sqlite3
import sys

conn = sqlite3.connect(sys.argv[1])
try:
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
finally:
    conn.close()
if result != "ok":
    raise SystemExit(f"восстановленная база повреждена: {result}")
PY
  mv "$target.restore-$STAMP" "$target"
  log "SQLite восстановлена: $target"
}

restore_postgres() {
  local url="${DATABASE_URL/postgresql+psycopg/postgresql}"
  command -v psql >/dev/null || fail "нужен psql"
  log "Восстанавливаю PostgreSQL из $DB_BACKUP"
  gzip -dc "$DB_BACKUP" | psql --dbname="$url" -v ON_ERROR_STOP=1 >/dev/null
  log "PostgreSQL восстановлен"
}

restore_media() {
  local source="${MEDIA_ROOT:-$ROOT/backend/media}"
  if [[ "$source" != /* ]]; then
    source="$ROOT/backend/${source#./}"
  fi
  local safety="$source.pre-restore-$STAMP.tar.gz"
  if [[ -d "$source" ]]; then
    log "Сохраняю текущие медиа: $safety"
    tar czf "$safety" -C "$(dirname "$source")" "$(basename "$source")"
    rm -rf "$source"
  fi
  mkdir -p "$(dirname "$source")"
  tar xzf "$MEDIA_BACKUP" -C "$(dirname "$source")"
  log "Медиа восстановлены: $source"
}

verify

if [[ "$VERIFY_ONLY" == "1" ]]; then
  exit 0
fi

confirm
[[ -n "$DB_BACKUP" ]] || fail "для восстановления нужен --db"
case "$DATABASE_URL" in
  sqlite:*)
    case "$DB_BACKUP" in
      *.sqlite3.gz|*.db.gz) restore_sqlite "$(resolve_sqlite_path "$DATABASE_URL")" ;;
      *) fail "для SQLite нужен файл .sqlite3.gz, получен $DB_BACKUP" ;;
    esac
    ;;
  postgresql:*)
    case "$DB_BACKUP" in
      *.sql.gz) restore_postgres ;;
      *) fail "для PostgreSQL нужен файл .sql.gz, получен $DB_BACKUP" ;;
    esac
    ;;
  *) fail "неизвестный тип DATABASE_URL: ${DATABASE_URL%%:*}" ;;
esac

[[ -n "$MEDIA_BACKUP" ]] && restore_media
log "Восстановление завершено. Запустите приложение и проверьте /api/health и ключевые страницы."
