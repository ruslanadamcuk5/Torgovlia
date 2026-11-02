# Деплой на PythonAnywhere (Free EU)

Текущий production: **https://virusadk.eu.pythonanywhere.com**

## Что где лежит

| Что | Путь |
| --- | --- |
| Код | `/home/virusadk/rybnaya-lavka` |
| Python-пакеты | `/home/virusadk/pa-packages2` |
| SQLite | `/home/virusadk/rybnaya-lavka/backend/data/rybnaya.db` |
| Фото и баннеры | `/home/virusadk/rybnaya-lavka/backend/media/` |
| Собранный фронтенд | `/home/virusadk/rybnaya-lavka/frontend/dist/` |
| APK | `/home/virusadk/rybnaya-lavka/frontend/dist/downloads/rybnaya-lavka.apk` |
| WSGI | `/var/www/virusadk_eu_pythonanywhere_com_wsgi.py` |

WSGI-файл оборачивает FastAPI через `a2wsgi.ASGIMiddleware`. Middleware создаётся
лениво внутри `application`, чтобы не было конфликта event loop после fork.

## Статические файлы

В веб-приложении настроены mapping'и:

- `/assets/` → `frontend/dist/assets/`
- `/icons/` → `frontend/dist/icons/`
- `/media/` → `backend/media/`
- `/downloads/` → `frontend/dist/downloads/`

`/downloads/` отдаёт APK с MIME `application/vnd.android.package-archive`.

## Переменные окружения

Файл `.env` лежит рядом с backend и **не коммитится**. Основные ключи:

- `PUBLIC_BASE_URL` — публичный HTTPS-адрес;
- `DATABASE_URL` — `sqlite:///.../backend/data/rybnaya.db`;
- `MEDIA_ROOT` — каталог загрузок;
- `CORS_ORIGINS` — домены сайта и `https://localhost` для Android WebView;
- `SMS_PROVIDER=console` и `SMS_EXPOSE_CODE=true` — демо-режим SMS;
- `ADMIN_PHONE`, `ADMIN_PASSWORD`, `ADMIN_NAME` — первый администратор;
- `SEED_DEMO`, `SEED_CATALOG` — начальное заполнение.

Для реальных SMS на платном тарифе замените `SMS_PROVIDER` и добавьте ключи
провайдера. На Free-тарифе исходящие запросы к SMS.BY недоступны.

## Обновление сайта

1. Соберите фронтенд:

```powershell
cd frontend
npm run build
```

2. Загрузите содержимое `frontend/dist/` в тот же каталог на сервере.
   Файлы `assets/`, `icons/`, `index.html`, `sw.js`, `version.json` должны
   обновиться вместе.
3. Перезагрузите веб-приложение (Web → Reload) или через API
   `POST /api/v0/user/{user}/webapps/{domain}/reload/`.

`version.json` содержит build id. Открытые PWA-клиенты увидят баннер
«Доступна новая версия сайта» и обновятся по кнопке.

## Обновление Android APK

1. Поднимите `versionCode` и `versionName` в
   `frontend/android/app/build.gradle` и `version` в `frontend/package.json`.
2. Соберите APK по инструкции `docs/ANDROID.md`.
3. Загрузите его как `frontend/dist/downloads/rybnaya-lavka.apk`.
4. В `/admin → Настройки → Приложение` обновите:
   - ссылку `/downloads/rybnaya-lavka.apk`;
   - версию (например, `1.0.1`);
   - размер файла.
5. Установленное приложение покажет баннер обновления при следующем запуске
   или возврате в приложение.

## Бэкап

Перед обновлением скачайте:

- `backend/data/rybnaya.db`;
- `backend/media/`;
- `.env` (хранить в менеджере секретов).

SQLite-файл нельзя копировать во время активной записи. На Free-тарифе проще
ненадолго остановить веб-приложение, скачать файл и включить обратно.

## Ограничения Free-тарифа

- веб-приложение нужно продлевать каждые 3 месяца (кнопка
  «Run until 3 months from today»);
- нет доступа к внешним SMS-шлюзам;
- ограничены диск, трафик и CPU;
- домен вида `*.eu.pythonanywhere.com`.

## Чек-лист перед реальным запуском

- [ ] Заменить демо-телефон, e-mail и соцсети в `/admin → Настройки`.
- [ ] Указать реальные юридическое наименование, УНП и адрес.
- [ ] Указать точный номер павильона.
- [ ] Сменить пароль администратора и создать продавца.
- [ ] Проверить статьи, цены, наличие и сроки бронирования.
- [ ] Подключить реальный SMS-провайдер или согласовать демо-режим.
- [ ] Продлить веб-приложение до нужной даты.
