# Android-приложение покупателя

Приложение собрано на Capacitor 6: внутри — тот же React-сайт, снаружи — нативная
оболочка Android. Отдельный код покупателя поддерживать не нужно.

- Название: **Рыбная лавка**
- Package ID: `by.rybnayalavka.app`
- minSdk: 24 (Android 7.0)
- compileSdk / targetSdk: 35 (Android 15)
- API: задаётся при сборке через `VITE_API_BASE_URL`
- Текущий production API: `https://virusadk.eu.pythonanywhere.com/api`

## 1. Требования

- JDK 17 (не 21 и не 8)
- Android Studio (последняя стабильная)
- Android SDK Platform 35 и Build-Tools 35
- Node.js 20–22

Проверьте:

```bash
java -version
node -v
```

В Android Studio: **Tools → SDK Manager → Android 15 (API 35)**.

## 2. Сборка веб-части под приложение

В приложении нельзя использовать относительный `/api`: WebView откроет
`https://localhost/api`. Всегда передавайте полный HTTPS-адрес.

PowerShell:

```powershell
cd frontend
$env:VITE_API_BASE_URL="https://virusadk.eu.pythonanywhere.com/api"
npm run build
npx cap sync android
npx cap open android
```

Linux/macOS:

```bash
cd frontend
VITE_API_BASE_URL=https://virusadk.eu.pythonanywhere.com/api npm run build
npx cap sync android
npx cap open android
```

Проверьте `frontend/android/app/src/main/assets/capacitor.config.json`: там должен
быть `"androidScheme": "https"`.

> После любого изменения фронтенда повторяйте `npm run build && npx cap sync android`.
> `npx cap sync` копирует свежий `dist` в Android-проект.

## 3. Запуск на телефоне

1. Включите на телефоне «Для разработчиков» и отладку по USB.
2. Подключите телефон, разрешите отладку.
3. В Android Studio выберите устройство и нажмите Run.

Для локального backend по HTTP есть два безопасных варианта:

- HTTPS-туннель (Cloudflare Tunnel, ngrok) на локальный порт 8000;
- debug-сборка с HTTP: в `android/app/src/debug/AndroidManifest.xml` уже разрешён
  cleartext, а mixed content включается только переменной окружения:

```powershell
$env:CAPACITOR_ALLOW_HTTP="true"
$env:VITE_API_BASE_URL="http://192.168.1.10:8000/api"
npm run build
npx cap sync android
```

**Не переносите `CAPACITOR_ALLOW_HTTP=true` в release.** В release HTTP запрещён.

Release-сборка запрещает HTTP: `android:usesCleartextTraffic="false"`.

## 4. Иконка и splash

Иконки и заставки уже сгенерированы из `frontend/public/icons/icon-512.png`.
Пересоздать после смены логотипа:

```bash
backend/.venv/Scripts/python.exe scripts/generate_android_assets.py
```

Скрипт обновляет `frontend/android/app/src/main/res/mipmap-*` и `drawable-*`.

## 5. Подпись release

В проекте уже настроена подпись через локальные файлы:

- `frontend/android/rybnaya-lavka-release.jks` — keystore;
- `frontend/android/keystore.properties` — пароли и alias (в `.gitignore`).

`app/build.gradle` читает `keystore.properties` и автоматически подписывает
`assembleRelease`. Оба файла **не коммитятся**. Обязательно сохраните их копию
вне репозитория: без этого keystore нельзя выпустить обновление поверх
установленной версии.

Сборка:

```bash
cd frontend/android
./gradlew bundleRelease   # AAB для Google Play
./gradlew assembleRelease # APK для прямой установки
```

Windows: `gradlew.bat assembleRelease`.

Результат: `app/build/outputs/bundle/release/app-release.aab` или
`app/build/outputs/apk/release/app-release.apk`.

Храните keystore и пароли в менеджере секретов. Потеря keystore не позволит
обновлять приложение в Google Play и устанавливать APK поверх текущей версии.

## 6. Публикация в Google Play

Перед публикацией:

1. Поднимите `versionCode` (целое число) и `versionName` в `frontend/android/app/build.gradle`.
2. Укажите политику конфиденциальности: `https://virusadk.eu.pythonanywhere.com/legal/privacy`.
3. В Play Console заполните **Data safety**: приложение собирает имя, телефон, e-mail
   (по желанию), историю броней; передаёт данные по HTTPS; не продаёт данные.
4. Укажите **Account deletion**: `https://virusadk.eu.pythonanywhere.com/account`
   (раздел «Профиль → Удаление аккаунта»).
5. Создайте тестового покупателя для рецензентов Google:
   `/admin/users → Создать доступ → Покупатель`. Пароль передайте в разделе
   **App access** Play Console. Такой аккаунт уже имеет подтверждённый телефон,
   поэтому проверяющий сможет оформить бронь без SMS.
6. Возрастной рейтинг: 3+ / 6+ (нет алкоголя, табака, азартных игр).
7. Укажите, что приложение не содержит рекламы и встроенных покупок.
8. Проверьте, что все внешние ссылки (TikTok, Instagram, YouTube) открываются.

Google Play может потребовать более свежий targetSdk. На момент подготовки проекта
используется API 35; перед публикацией сверьтесь с актуальными требованиями
Play Console и при необходимости поднимите `compileSdkVersion`/`targetSdkVersion`
в `frontend/android/variables.gradle`.

## 7. Обновление приложения

1. Поднимите `versionCode` (целое +1) и `versionName` в
   `frontend/android/app/build.gradle`, а также `version` в `frontend/package.json`.
2. Соберите веб-часть и APK:

```powershell
cd frontend
$env:VITE_API_BASE_URL="https://virusadk.eu.pythonanywhere.com/api"
npm run build
npx cap sync android
cd android
.\gradlew.bat assembleRelease
```

3. Загрузите `app/build/outputs/apk/release/app-release.apk` на сервер как
   `/home/virusadk/rybnaya-lavka/frontend/dist/downloads/rybnaya-lavka.apk`.
4. В `/admin → Настройки → Приложение` укажите новую версию и размер APK.
   Поле «Ссылка на APK»: `/downloads/rybnaya-lavka.apk`.

Установленное приложение проверяет `/api/site` при запуске, возврате в
приложение и раз в 30 минут. Если `android_app_version` на сервере выше
установленной, появляется баннер «Доступна новая версия» со ссылкой на APK.
Ссылка открывается в системном браузере Android, поэтому загрузка и установка
работают штатно.

Для PWA обновление определяется по `/version.json`: при новом `build`
появляется баннер «Доступна новая версия сайта».
