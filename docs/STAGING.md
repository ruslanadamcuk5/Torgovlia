# Staging: отдельный стенд и дымовой тест

Staging нужен, чтобы проверять миграции, входы, демо и новые сервисы до
обновления боевого сайта. Это **отдельная база и отдельный домен**, а не копия
production на том же диске.

## Чем отличается от production и демо

| | Staging | Production | Демо на alwaysdata |
|---|---|---|---|
| Домен | `staging.example.by` | домен клиента | `*.alwaysdata.net` |
| База | отдельная SQLite/PostgreSQL | PostgreSQL | SQLite |
| `DEMO_MODE` | `false` | `false` | `true` |
| `X-Tenant-Slug` | `false` | `false` | `true` |
| SMS | `console` (код в лог) | реальный провайдер | `console` |
| Данные | можно сбросить | боевые | автосброс 24 часа |
| Пароли | стендовые | уникальные | `ChangeMe123!` |

## Поднять staging на сервере

1. Скопируйте `.env.staging.example` в `backend/.env` и заполните `CHANGE_ME`.
2. Создайте отдельную базу. Для SQLite каталог `data/` создаётся сам.
3. Примените миграции и запустите приложение:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
```

4. Настройте nginx/HTTPS и DNS:
   - `staging.example.by` — сайт продаж и панель платформы;
   - `<slug>.staging.example.by` — магазины (`rybnaya`, `odezhda`, ...);
   - либо оставьте один домен и включите `DEMO_MODE=true` только на стенде.

`start.sh` на alwaysdata сам применяет миграции и запускает `uvicorn`; для
staging на alwaysdata создайте отдельный сайт и отдельный каталог, чтобы не
пересекаться с демо.

## Дымовой тест

Скрипт `scripts/smoke.py` использует только стандартную библиотеку Python.
Он проверяет:

- `/api/health`, `/`, `/new`, `/shop/<slug>`;
- `/api/site` и выбранный магазин;
- вход владельца магазина и ключевые `/api/admin/*`;
- при `--full` — сертификаты, регулярные заказы, задачи, CRM и журнал;
- вход владельца платформы и `/api/platform/stats`, `/api/platform/tenants`.

### Staging с поддоменами

```bash
DEMO_ADMIN_PHONE=+375291112233 \
DEMO_ADMIN_PASSWORD='...' \
PLATFORM_ADMIN_PHONE=+375291110000 \
PLATFORM_ADMIN_PASSWORD='...' \
python3 scripts/smoke.py \
  --base-url https://staging.example.by \
  --host rybnaya.staging.example.by \
  --full
```

### Демо на alwaysdata (один origin)

```bash
python3 scripts/smoke.py \
  --base-url https://torg.alwaysdata.net \
  --demo --tenant odezhda --full
```

Демо-пароли по умолчанию — `ChangeMe123!`; их обязательно сменить перед
продакшеном. Для staging передавайте пароли через переменные окружения, чтобы
они не остались в истории команд.

Код возврата `1` означает, что хотя бы одна проверка не прошла. Сервисы,
которые не подключены на стенде, при `--full` пропускаются с пометкой `SKIP`.

## Что проверять на staging перед релизом

- [ ] `alembic upgrade head` проходит на копии боевой базы.
- [ ] `scripts/smoke.py` зелёный.
- [ ] Вход владельца, продавца и покупателя; смена пароля.
- [ ] Создание заказа, смена статуса, отчёт и CSV.
- [ ] Демо-магазин: витрина, админка, все включённые сервисы.
- [ ] Бэкап и `deploy/restore.sh --verify-only` (см. `docs/OPERATIONS.md`).
- [ ] Нет боевых секретов и боевых SMS в `.env`.

## CI

В `.github/workflows/ci.yml` job `smoke` поднимает приложение на SQLite,
применяет миграции, ждёт `/api/health` и запускает
`scripts/smoke.py --demo --full`. Job `backend` дополнительно делает бэкап
тестовой базы и проверяет восстановление через `deploy/restore.sh --verify-only`.
