# Эксплуатация и диагностика

## Состав production

- `app` — FastAPI, отдаёт API, собранный React и `/media`.
- `db` — PostgreSQL 16.
- nginx на хосте — HTTPS, проксирование, лимиты.
- Тома Docker: `pgdata` (БД) и `media` (фото товаров и баннеров).

## Ежедневные проверки

```bash
curl -fsS https://rybnaya-lavka.by/api/health
docker compose ps
docker compose logs --since=1h app
```

Ожидаемый ответ health:

```json
{"status":"ok","environment":"production","version":"1.0.0"}
```

## Логи и перезапуск

```bash
docker compose logs -f app
docker compose restart app
docker compose up -d --build
```

Логи nginx: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`.

## Обновление

```bash
cd /opt/rybnaya-lavka
./deploy/backup.sh
git pull
docker compose up -d --build
curl -fsS https://rybnaya-lavka.by/api/health
```

Если менялись модели БД, применяйте миграции Alembic:

```bash
cd backend
alembic upgrade head
```

Проверить текущую ревизию: `alembic current`, историю: `alembic history`.
Перед обновлением всегда есть свежий бэкап. Для существующей базы миграция
`3fac88ebce39` создаёт арендатора по умолчанию и привязывает к нему старые данные.

## Бэкап

Скрипт поддерживает обе схемы:

- **SQLite** (alwaysdata, staging, небольшой сервер) — копия через
  `sqlite3.backup`, проверка `PRAGMA integrity_check`;
- **PostgreSQL** — `pg_dump` через `docker compose` или по `DATABASE_URL`;
- **медиа** — `backend/media` (или том контейнера `app`);
- **манифест и SHA-256** — чтобы заметить повреждение при выгрузке.

```bash
./deploy/backup.sh
```

Файлы: `backups/db-*.sqlite3.gz` или `backups/db-*.sql.gz`,
`backups/media-*.tar.gz`, `backups/manifest-*.txt`,
`backups/SHA256SUMS-*.txt`. Хранится 14 копий каждого типа
(`BACKUP_KEEP`). Каталог `backups/` создаётся с правами `700`.

Настройте cron (для alwaysdata путь `/opt/rybnaya-lavka` замените на свой):

```cron
15 3 * * * /opt/rybnaya-lavka/deploy/backup.sh >> /var/log/rybnaya-backup.log 2>&1
30 3 * * * cd /opt/rybnaya-lavka/backend && .venv/bin/python ../scripts/pd_cleanup.py --apply >> /var/log/rybnaya-pd.log 2>&1
```

Скрипт читает `.env` из корня или `backend/.env`; для staging укажите
`BACKUP_ENV_FILE=/path/to/.env`. Обязательно копируйте `backups/` на другой
сервер или в объектное хранилище: копия на том же диске не защищает от потери
сервера.

### Проверка копии без восстановления

Безопасно запускать на работающем сервере:

```bash
./deploy/restore.sh --verify-only \
  --db backups/db-20261109-031500.sqlite3.gz \
  --media backups/media-20261109-031500.tar.gz
```

Скрипт проверяет gzip, целостность SQLite, наличие таблиц и читаемость архива
медиа, печатает время проверки. Это и есть учения по восстановлению: делайте их
раз в месяц и записывайте результат и время.

### Восстановление SQLite (alwaysdata, staging)

1. Остановите приложение (на alwaysdata — сайт в панели, локально — `Ctrl+C`).
2. Запустите восстановление; текущая база сохранится рядом с суффиксом
   `.pre-restore-*`:

```bash
./deploy/restore.sh \
  --db backups/db-20261109-031500.sqlite3.gz \
  --media backups/media-20261109-031500.tar.gz \
  --yes
```

3. Запустите приложение и проверьте `/api/health`, витрину и админку.
4. Убедитесь, что `alembic current` совпадает с версией кода.

### Восстановление PostgreSQL (docker compose)

```bash
docker compose stop app
./deploy/restore.sh --db backups/db-20261109-031500.sql.gz --yes
docker compose start app
```

Скрипт использует `psql` и `DATABASE_URL`; для docker compose без локального
`psql` можно выполнить вручную:

```bash
gunzip -c backups/db-20261109-031500.sql.gz | \
  docker compose exec -T db psql -U rybnaya -d rybnaya
```

### Восстановление изображений отдельно

```bash
./deploy/restore.sh --media backups/media-20261109-031500.tar.gz --yes
```

После восстановления перезапустите `app` и проверьте, что фото товаров
открываются по `/media/...`.

### Учения по восстановлению (P0)

Минимальный сценарий раз в месяц:

```bash
time ./deploy/backup.sh
time ./deploy/restore.sh --verify-only --db backups/db-*.sqlite3.gz
```

Для полного учения восстановите копию в отдельный файл/базу, запустите
приложение на свободном порту и прогоните `scripts/smoke.py`. Результат
(дата, размер копии, время восстановления, кто проверял) запишите в журнал
инцидентов или в этот документ.


## Частые проблемы

### «Не удалось отправить SMS»

- Проверьте `SMS_PROVIDER`, токен, отправителя и баланс провайдера.
- В production `SMS_EXPOSE_CODE` должен быть `false`.
- Посмотрите `docker compose logs app | grep -i sms`.
- SMS.BY: проверьте, что номер отправителя согласован.
- WebSMS: проверьте `SMS_API_URL`, логин и пароль.

### Покупатель не видит свободное время

- Проверьте режим работы и выходные в `/admin/settings`.
- `LEAD_TIME_MINUTES` — минимальное время до получения.
- `SLOT_CAPACITY` — сколько броней на один слот.
- `BOOKING_DAYS_AHEAD` — глубина бронирования.
- Время сервера должно быть корректным; проект сам считает Беларусь как UTC+3.

### QR ведёт на localhost

- В `.env` установите `PUBLIC_BASE_URL=https://rybnaya-lavka.by`.
- Перезапустите app: `docker compose restart app`.
- Перегенерируйте и перепечатайте QR.

### Фото не отображаются в Android

- В APK должен быть задан абсолютный `VITE_API_BASE_URL=https://rybnaya-lavka.by/api`.
- `assetUrl()` добавляет origin к `/media/...`; относительный `/api` в WebView не работает.
- Проверьте, что nginx проксирует `/media/`.

### Ошибка 413 при загрузке фото

- Увеличьте `client_max_body_size` в nginx.
- Проверьте `UPLOAD_MAX_MB` в `.env` (по умолчанию 8 МБ).

### Забыт пароль администратора

Создайте нового администратора или сбросьте пароль скриптом из `scripts/`:

```bash
cd backend
.venv/bin/python ../scripts/reset_password.py +375291112233 'НовыйПароль123'
```

Windows:

```powershell
cd backend
.\.venv\Scripts\python.exe ..\scripts\reset_password.py +375291112233 "НовыйПароль123"
```

Скрипт требует доступ к той же БД, что и приложение.

## Безопасность

- Не публикуйте `.env`, keystore и бэкапы.
- Ограничьте доступ к серверу по SSH-ключам, отключите вход по паролю.
- Обновляйте Docker-образы и системные пакеты.
- Не запускайте `DEBUG=true` в production.
- Один администратор — минимум; для продавца используйте роль `seller`.
- Проверяйте `/admin` журнал действий после смены персонала.
- При подозрении на утечку смените `SECRET_KEY` (все сессии станут недействительны),
  пароли администраторов и токены SMS-провайдера.

## Мониторинг

Минимально:

- внешний ping `https://rybnaya-lavka.by/api/health` раз в минуту;
- алерт на 5xx в nginx;
- алерт на заполнение диска (медиа и бэкапы);
- ежедневная проверка наличия свежего бэкапа;
- раз в месяц — тестовый заказ и проверка SMS.

## Контакты для пользователей

На сайте в `/admin/settings` должен быть реальный телефон павильона и часы работы.
Он показывается в шапке, подвале, на странице контактов и в SMS-подсказках.
