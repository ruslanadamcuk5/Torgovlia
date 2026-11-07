# Демо-стенд на alwaysdata

Бесплатный тариф alwaysdata используется как витрина разработки: на нём
крутится вся платформа Torgovlia (сайт продаж, панель платформы и демо-магазины),
а не отдельная «Рыбная лавка».

## Что нужно от владельца

1. Зарегистрировать бесплатный аккаунт: <https://www.alwaysdata.com/en/register/?p=2012>.
2. Создать API-токен: **Profile → Tokens → Create** (права read/write).
3. Передать имя аккаунта и токен.

Токен даёт полный доступ к аккаунту. Его можно отозвать сразу после деплоя.
Скрипт не печатает токен и не сохраняет его в проекте.

## Деплой одной командой

```bash
cd /root/workspace/torgovlia
export ALWAYSDATA_TOKEN='<токен>'
python3 deploy/alwaysdata/deploy.py --account <account>
```

Скрипт (`deploy.py`, только стандартная библиотека + системный `ssh`):

1. проверяет аккаунт по API;
2. собирает frontend с адресом платформы и демо-витринами;
3. создаёт FTP-пользователя `<account>_deploy` и загружает проект;
4. создаёт SSH-пользователя и добавляет ключ `.deploy/alwaysdata_ed25519.pub`;
5. ставит Python-зависимости в `backend/.venv` (если SSH доступен);
6. создаёт сайт типа **User program** с командой
   `bash /home/<account>/torgovlia/start.sh` (если на аккаунте уже есть
   стартовый PHP-сайт на `<account>.alwaysdata.net`, он переиспользуется и
   переводится в `user_program`, а не дублируется);
7. создаёт `backend/.env` при первом деплое;
8. при каждом запуске применяет миграции Alembic и поднимает uvicorn;
9. перезапускает сайт и проверяет `/api/health`.

Полезные параметры:

| Параметр | Назначение |
| --- | --- |
| `--domain shop.example.by` | свой домен вместо `<account>.alwaysdata.net` |
| `--extra-address www.example.by` | дополнительный адрес (можно несколько) |
| `--skip-build` | не пересобирать frontend |
| `--skip-upload` | только сайт и окружение |
| `--skip-install` | не ставить зависимости по SSH |
| `--force-env` | перезаписать `backend/.env` |
| `--wait 300` | дольше ждать первый запуск |
| `--dry-run` | показать план без изменений |

Состояние деплоя (пароли, SSH-ключ, id сайта) лежит в `.deploy/` и не
коммитится. Повторный запуск идемпотентен: сайт, FTP и `.env` переиспользуются.

## Адреса демо-стенда

| Что | Адрес |
| --- | --- |
| Сайт продаж | `https://<account>.alwaysdata.net/start` |
| Вход в панель платформы | `https://<account>.alwaysdata.net/platform/login` |
| Демо-магазин «Рыбная лавка» | `https://<account>.alwaysdata.net/shop/rybnaya` |
| Демо-магазин «Цветочная лавка» | `https://<account>.alwaysdata.net/shop/flowers` |
| Демо-магазин «Мясная лавка» | `https://<account>.alwaysdata.net/shop/meat` |

Демо-логины по умолчанию (смените перед реальным запуском):

- платформа: `+375291110000` / `ChangeMe123!`;
- магазины: `+375291112233`, `+375291112266`, `+375291112277` / `ChangeMe123!`.

## Почему `/shop/<slug>`, а не поддомены

На бесплатном alwaysdata нельзя добавить wildcard `*.account.alwaysdata.net`:
DNS-зоной `alwaysdata.net` управляет хостинг. Поэтому один origin обслуживает
и платформу, и витрины:

- `/start`, `/platform/*` — сайт продаж и панель;
- `/shop/<slug>/...` — витрина выбранного магазина;
- frontend запоминает магазин в `localStorage` и добавляет к API-запросам
  заголовок `X-Tenant-Slug`;
- backend принимает заголовок только при `DEMO_MODE=true` (на боевом
  мультидоменном сайте флаг выключен).

При подключении своего домена и wildcard-поддоменов демо-режим отключается,
а магазины открываются как `<slug>.domain.by`.

## Переменные окружения

`deploy.py` создаёт `backend/.env` со значениями:

```dotenv
ENVIRONMENT=production
DEBUG=false
PUBLIC_BASE_URL=https://<account>.alwaysdata.net
CORS_ORIGINS=https://<account>.alwaysdata.net,http://<account>.alwaysdata.net

PLATFORM_HOST=<account>.alwaysdata.net
PLATFORM_BASE_DOMAIN=<account>.alwaysdata.net
DEFAULT_TENANT_SLUG=rybnaya
TENANT_HEADER_ENABLED=true
DEMO_MODE=true

DATABASE_URL=sqlite:///./data/torgovlia.db
MEDIA_ROOT=media
SMS_PROVIDER=console
SMS_EXPOSE_CODE=true
SEED_DEMO=true
SEED_CATALOG=true
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Telegram-алерты необязательны: без токена сводка доступна в панели
«Запуск и мониторинг», но не отправляется в чат.

`SMS_EXPOSE_CODE=true` и `DEMO_MODE=true` — только для стенда. Для реального
запуска нужен договор с SMS-провайдером, PostgreSQL и отключённый демо-режим.

## Ручной деплой без API-токена

1. Создать сайт **Web → Sites → Add a site**:
   - Type: `User program`;
   - Command: `bash /home/<account>/torgovlia/start.sh`;
   - Working directory: `/home/<account>/torgovlia`;
   - Environment: `PYTHON_VERSION=3.12 PYTHONUNBUFFERED=1`.
2. Загрузить проект по SFTP в `/home/<account>/torgovlia`
   (без `backend/.venv`, `backend/data`, `backend/media`, `node_modules`).
3. Собрать frontend локально с переменными:
   ```bash
   cd frontend
   VITE_API_BASE_URL=/api \
   VITE_PLATFORM_HOSTS=<account>.alwaysdata.net \
   VITE_DEMO_STOREFRONTS=1 \
   npm run build
   ```
4. Создать `backend/.env` по образцу выше.
5. Перезапустить сайт. `start.sh` сам создаст `.venv` и поставит зависимости
   при первом запросе (это может занять 1–2 минуты).

## Проверка и обновление

```bash
curl -fsS https://<account>.alwaysdata.net/api/health
curl -fsS https://<account>.alwaysdata.net/api/site
```

Логи сайта: `/home/<account>/admin/logs/sites/`.
Логи HTTP: `/home/<account>/admin/logs/http/`.

Обновление — повторный запуск `deploy.py`. База (`backend/data`) и загруженные
файлы (`backend/media`) не перезаписываются, `.env` сохраняется без
`--force-env`.

## Ограничения бесплатного тарифа

- 1 ГБ диска, 256 МБ RAM, 1/4 CPU;
- сайт останавливается после 30 минут без запросов и поднимается при
  следующем обращении;
- нет root и фоновых воркеров;
- SQLite подходит для демо, но не для нагрузки и параллельных оплат.

Для пилота с реальными магазинами нужен VPS или платный тариф с PostgreSQL,
резервным копированием и мониторингом.

## Если сайт не поднялся

1. Открыть `/home/<account>/admin/logs/sites/` — ошибки запуска.
2. Проверить, что `backend/.venv/bin/uvicorn` существует и зависимости
   установлены.
3. Убедиться, что сайт слушает `$IP` и `$PORT` (это делает `start.sh`).
4. Проверить `backend/.env`: `PLATFORM_HOST`, `SECRET_KEY`, `DATABASE_URL`.
5. Перезапустить сайт в **Web → Sites → Restart**.

Типовые причины: неверная версия Python, не хватило места на диске,
занятый адрес другим сайтом, синтаксическая ошибка в `.env`.
