# Деплой на alwaysdata (бесплатный тариф)

Выбранный бесплатный хостинг: **alwaysdata Free**.

Почему он подходит:

- 1 ГБ SSD с постоянным хранением файлов;
- 256 МБ RAM и 1/4 CPU;
- поддержка ASGI/FastAPI через тип сайта **User program** (Uvicorn);
- бесплатный HTTPS-адрес вида `https://<account>.alwaysdata.net`;
- SQLite и загруженные изображения сохраняются между перезапусками;
- не требуется банковская карта.

Ограничения бесплатного тарифа: 1 ГБ диска, 256 МБ RAM, нет root-доступа, сайт может останавливаться после 30 минут без запросов и запускаться при следующем обращении.

## Что нужно от владельца

1. Зарегистрировать бесплатный аккаунт:  
   <https://www.alwaysdata.com/en/register/?p=2012>
2. Прислать **имя аккаунта** (например, `rybnaya-lavka`).
3. Создать API-токен: **Profile → Tokens → Create**.  
   Прислать токен. После деплоя токен можно отозвать.
4. Если не хотите передавать токен — создайте SSH-пользователя и добавьте публичный ключ из `docs/OPERATIONS.md`; тогда деплой выполняется вручную.

> API-токен даёт доступ к аккаунту. Передавайте его только в защищённом канале и отзывайте после завершения деплоя.

## Параметры сайта

В панели alwaysdata: **Web → Sites → Add a site**.

| Поле | Значение |
| --- | --- |
| Name | `Рыбная лавка` |
| Addresses | `<account>.alwaysdata.net` |
| Type | `User program` |
| Command | `bash start.sh` |
| Working directory | `/home/<account>/rybnaya-lavka` |
| SSL | Force HTTPS |

`start.sh` уже лежит в этом каталоге и будет загружен в корень проекта. Он запускает:

```bash
backend/.venv/bin/uvicorn app.main:app --host "$IP" --port "$PORT" \
  --proxy-headers --forwarded-allow-ips="*"
```

## Переменные окружения

Файл `backend/.env` создаётся при деплое и **не коммитится в Git**. Обязательные значения:

```dotenv
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<сгенерированный секрет>
PUBLIC_BASE_URL=https://<account>.alwaysdata.net
CORS_ORIGINS=https://<account>.alwaysdata.net
DATABASE_URL=sqlite:///./data/rybnaya.db
MEDIA_ROOT=media
ADMIN_PHONE=+375291112233
ADMIN_PASSWORD=<сильный пароль>
ADMIN_NAME=Владелец
SEED_DEMO=false
SEED_CATALOG=true
SMS_PROVIDER=console
SMS_EXPOSE_CODE=true
```

`SMS_EXPOSE_CODE=true` — только для демонстрации: код показывается на экране вместо отправки SMS. Для реального запуска нужен договор с SMS-провайдером (например, SMS.BY), после чего указываются `SMS_API_TOKEN`/`SMS_LOGIN`/`SMS_PASSWORD`, а `SMS_EXPOSE_CODE` ставится `false`.

## Проверка после деплоя

```bash
curl -fsS https://<account>.alwaysdata.net/api/health
curl -fsS https://<account>.alwaysdata.net/api/site
```

Админка:

```text
https://<account>.alwaysdata.net/admin
```

Логи сайта на alwaysdata:

```text
/home/<account>/admin/logs/sites/
```

## Обновление сайта

1. Собрать фронтенд:
   ```bash
   cd frontend
   npm run build
   ```
2. Загрузить проект по SSH/SFTP в `/home/<account>/rybnaya-lavka`.
3. Перезапустить сайт в **Web → Sites**.
4. Проверить `/api/health`.

Базу и загруженные изображения не перезаписывать: они находятся в `backend/data` и `backend/media`.
