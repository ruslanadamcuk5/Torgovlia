# Рыбная лавка — сайт и мобильные приложения

Сайт и мобильное приложение рыбного павильона на рынке «Алексеевский» в Барановичах.
Покупатель выбирает рыбу, указывает вес, дату и время самовывоза, подтверждает телефон
кодом из SMS и получает бронь. Оплата — только в павильоне, доставки нет.

- Сайт: FastAPI + React 18 + TypeScript + Vite
- Приложение покупателя: Capacitor Android и iOS (тот же React-код) + PWA
- База: PostgreSQL в production, SQLite для локальной разработки
- QR-коды на сайт и на статью о каждой рыбе
- Админ-панель и отдельный мобильный режим продавца

> Юридические реквизиты, цены и наличие в демо-данных — примеры. Перед запуском
> заполните реальные данные в `/admin/settings` и проверьте чек-лист
> [`docs/COMPLIANCE-BY.md`](docs/COMPLIANCE-BY.md).

## Что реализовано

### Для покупателя
- Каталог с ценой за кг или за штуку, скидками, остатками и статусом «сегодня нет в наличии».
- Полная статья о каждом виде рыбы: происхождение, сезон, пищевая ценность, советы по приготовлению и хранению.
- Корзина с весом, минимальной суммой и проверкой остатков.
- Бронь на дату и время с ограничением мест на слот и временем подготовки.
- Обязательное подтверждение мобильного телефона по SMS — и для гостя, и для зарегистрированного покупателя.
- Гость может найти бронь по номеру и телефону; зарегистрированный видит историю в личном кабинете.
- Отмена брони покупателем до начала сборки.
- Удаление аккаунта с обезличиванием персональных данных.
- PWA-установка, Android APK и установка на iPhone/iPad через Safari.
- Страницы «Как забрать», «Контакты», политика персональных данных, правила бронирования, реквизиты, УНП в подвале.
- Крупные ссылки на TikTok, Instagram и YouTube.

### Для администратора
- Дашборд: новые брони, выручка, средний чек, остатки, топ товаров, журнал действий.
- Заказы: фильтры, карточка, смена статуса, комментарий, CSV-экспорт.
- Каталог: создание, редактирование, скрытие, наличие, остатки, скидки, категории, фото.
- Акции: скидки и «товар дня».
- Пользователи: роли покупатель / продавец / администратор, блокировка.
- Настройки: реквизиты, адрес, павильон, телефон, режим работы, баннеры, преимущества,
  правила бронирования, политика, тексты, SEO, ссылки на соцсети, карта.
- QR-коды: генерация, скачивание PNG, печать на A4.

### Для продавца
- Отдельный мобильный интерфейс `/seller` с крупными кнопками.
- Активные брони и быстрые действия «Подтвердить», «Готово», «Выдано», «Отклонить».
- Отметка наличия одним нажатием.
- Создание и редактирование товара, съёмка на камеру или выбор из галереи.

## Структура проекта

```
backend/              FastAPI, SQLAlchemy, тесты
  app/api/            публичные, auth, account, seller, admin
  app/services/       заказы, SMS, QR, настройки, загрузка файлов
  tests/              end-to-end тесты API
frontend/             React + Vite
  src/pages/          публичные страницы, админка, кабинет продавца
  src/components/     UI-компоненты
  android/            нативный проект Capacitor
deploy/               nginx, systemd, backup
docs/                 документация и юридический чек-лист
scripts/              генерация ассетов
Dockerfile            production-образ (backend + собранный frontend)
docker-compose.yml    app + PostgreSQL
```

## Быстрый старт (разработка)

Требования: Python 3.11–3.12, Node.js 20–22.

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

API: <http://localhost:8000/api/docs>  
Проверка: <http://localhost:8000/api/health>

По умолчанию `SMS_PROVIDER=console`: код печатается в консоль сервера и показывается
в форме как «Тестовый режим». Для реальных SMS заполните `.env` (см. ниже).

### 2. Frontend

Во втором терминале:

```bash
cd frontend
npm install
npm run dev
```

Сайт: <http://localhost:5173>. Vite проксирует `/api` и `/media` на `http://127.0.0.1:8000`.

### Демо-доступы

Создаются только при `SEED_DEMO=true`:

| Роль | Телефон | Пароль |
|---|---|---|
| Администратор | `+375291112233` | `ChangeMe123!` |
| Продавец | `+375291112244` | `Seller123!` |
| Покупатель | `+375291112255` | `Customer123!` |

**Смените пароль администратора сразу после первого входа.** Для production
установите `SEED_DEMO=false`, тогда демо-продавец и демо-покупатель не создаются.

### Наполнение каталога

При `SEED_CATALOG=true` пустая база один раз заполняется 15 видами рыбы со статьями.
Повторный запуск ничего не дублирует. Дальше товары редактируются в `/admin/catalog`:
цены, наличие, остатки, фото, статьи, категории. Чтобы начать с чистого каталога,
установите `SEED_CATALOG=false` до первого запуска.

## SMS

Подтверждение номера обязательно. Поддерживаются провайдеры:

- `console` — только разработка;
- `smsby` — SMS.BY, токен в `SMS_API_TOKEN`, отправитель в `SMS_SENDER`;
- `websms` — WebSMS.BY, логин/пароль/отправитель и **свой** `SMS_API_URL`.

В production обязательно:

```env
DEBUG=false
SMS_PROVIDER=smsby
SMS_EXPOSE_CODE=false
SMS_API_TOKEN=...
SMS_SENDER=...
```

Сервер сам ограничивает частоту: 60 секунд между кодами, 5 кодов в час на номер,
5 попыток ввода. Дополнительно настройте лимиты в nginx и SMS-провайдера.

## Production через Docker

Требования: VPS с Docker и Docker Compose, домен, открытые порты 80/443.

```bash
cp .env.production.example .env
# отредактируйте .env: домен, SECRET_KEY, пароли, SMS, администратор
docker compose up -d --build
docker compose logs -f app
```

`SECRET_KEY` сгенерируйте так:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Приложение слушает только `127.0.0.1:8000`. Наружу его публикует nginx:

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/rybnaya-lavka
sudo ln -s /etc/nginx/sites-available/rybnaya-lavka /etc/nginx/sites-enabled/
# замените rybnaya-lavka.by на свой домен
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d rybnaya-lavka.by -d www.rybnaya-lavka.by
```

Проверка:

```bash
curl https://rybnaya-lavka.by/api/health
```

В `.env` обязательно:

```env
PUBLIC_BASE_URL=https://rybnaya-lavka.by
CORS_ORIGINS=https://rybnaya-lavka.by,https://www.rybnaya-lavka.by
ENVIRONMENT=production
DEBUG=false
```

От `PUBLIC_BASE_URL` зависят QR-коды и ссылки в SMS.

### Production без Docker (systemd)

1. Разместите проект в `/opt/rybnaya-lavka`.
2. Создайте venv, установите `backend/requirements.txt`, соберите `frontend` (`npm ci && npm run build`).
3. Заполните `/opt/rybnaya-lavka/.env`.
4. Установите unit:

```bash
sudo cp deploy/rybnaya-lavka.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rybnaya-lavka
```

5. Настройте nginx из `deploy/nginx.conf` и TLS.
6. Права: `www-data` должен писать в `backend/data` и `backend/media`.

## Резервное копирование

Для Docker:

```bash
chmod +x deploy/backup.sh
./deploy/backup.sh
```

Скрипт сохраняет дамп PostgreSQL и изображения в `backups/`, хранит 14 копий.
Добавьте в cron и **обязательно** копируйте бэкапы на другой сервер/в облако.
Перед каждым обновлением делайте бэкап вручную.

Восстановление:

```bash
gunzip -c backups/db-YYYYMMDD-HHMMSS.sql.gz | \
  docker compose exec -T db psql -U rybnaya -d rybnaya
```

## Android-приложение

Подробно: [`docs/ANDROID.md`](docs/ANDROID.md). Кратко:

1. Установите JDK 17 и Android Studio с Android SDK 35.
2. Соберите фронтенд с **абсолютным** адресом API:

```powershell
cd frontend
$env:VITE_API_BASE_URL="https://rybnaya-lavka.by/api"
npm run build
npx cap sync android
npx cap open android
```

3. В Android Studio: Build → Generate Signed Bundle / APK.
4. Перед публикацией поднимите `versionCode`/`versionName` в `frontend/android/app/build.gradle`.

Важно: приложение работает только с HTTPS (`android:usesCleartextTraffic="false"`).
Если при сборке не задать `VITE_API_BASE_URL`, APK будет обращаться к несуществующему
`https://localhost/api`. Для локальной отладки используйте HTTPS-туннель либо
временную debug-сборку с разрешённым cleartext.

## iOS-приложение

На сайте доступна установка PWA на iPhone/iPad: Safari → «Поделиться» →
«На экран „Домой“». Это работает без App Store и Apple Developer.

Нативный проект Capacitor лежит в `frontend/ios/`. Для сборки IPA нужен Mac с Xcode
и Apple Developer Program. Прямая установка IPA из браузера, как APK, Apple
не разрешает. Подробно: [`docs/IOS.md`](docs/IOS.md).

```bash
cd frontend
VITE_API_BASE_URL=https://rybnaya-lavka.by/api npm run build
npx cap sync ios
npx cap open ios
```

Backend должен разрешать `capacitor://localhost` в `CORS_ORIGINS`.

## Обновление сайта

```bash
git pull
docker compose up -d --build
docker compose logs -f app
```

Схема БД создаётся автоматически при старте. Перед обновлением с изменениями моделей
сделайте бэкап. Для крупных проектов подключите Alembic.

## Безопасность

- Пароли — bcrypt, JWT с ограниченным сроком, отдельные короткоживущие токены телефона.
- SMS-код хранится только как HMAC, действует 5 минут, попытки ограничены.
- Проверка роли на каждом административном и seller-эндпоинте.
- Загрузка изображений: проверка MIME и содержимого, перекодирование в WebP, лимит размера.
- Защита от декомпрессионных бомб и автоматический поворот фото по EXIF.
- Ограничение попыток входа и запросов SMS.
- Security-заголовки, HSTS в production, HTTPS-only для Android.
- Аудит действий администратора и продавца.
- В production сервер не запустится с development `SECRET_KEY`, `DEBUG=true` или `http://` в `PUBLIC_BASE_URL`.

## Юридический запуск

Перед приёмом заказов:

1. Заполните в `/admin/settings` реальные `legal_name`, `УНП`, юридический адрес,
   телефон, павильон, режим работы, политику и правила бронирования.
2. Проверьте, что цены, наличие и состав совпадают с прилавком.
3. Заключите договор на торговое место, оформите медицинскую книжку, документы
   на партии рыбы и поверку весов/кассы.
4. Разместите информацию для потребителей в павильоне и онлайн.
5. Проверьте требования к персональным данным, рекламе и онлайн-торговле на дату запуска.

Полный чек-лист: [`docs/COMPLIANCE-BY.md`](docs/COMPLIANCE-BY.md). Это не юридическая
консультация: финальные документы согласуйте с юристом и бухгалтером.

## Документация

- [`docs/ANDROID.md`](docs/ANDROID.md) — сборка, подпись и публикация APK/AAB.
- [`docs/IOS.md`](docs/IOS.md) — iOS/PWA, сборка в Xcode, TestFlight и App Store.
- [`docs/COMPLIANCE-BY.md`](docs/COMPLIANCE-BY.md) — чек-лист для Беларуси.
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — запуск, обновления, бэкапы, диагностика.
- `/api/docs` — OpenAPI (только вне production).

## Лицензия

Проприетарный проект для владельца «Рыбной лавки». Все права reserved.
