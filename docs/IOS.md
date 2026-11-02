# iOS-приложение покупателя

В проекте есть два варианта для iPhone и iPad:

1. **PWA-установка с сайта** — работает уже сейчас, без App Store и без Apple Developer.
   На `/app` есть блок «iPhone и iPad»: Safari → «Поделиться» → «На экран „Домой“».
2. **Нативное приложение Capacitor** — исходный проект лежит в `frontend/ios/`.
   Для сборки и установки нужен Mac с Xcode и Apple Developer Program.

## Что уже подготовлено

- Bundle ID: `by.rybnayalavka.app`
- Display name: **Рыбная лавка**
- Версия: `1.0.0` (`MARKETING_VERSION`), сборка `1` (`CURRENT_PROJECT_VERSION`)
- Deployment target: iOS 13.0
- Устройства: iPhone и iPad
- Иконка приложения и splash-экран заменены на фирменные
- Production API: `https://virusadk.eu.pythonanywhere.com/api`
- WebView origin для CORS: `capacitor://localhost`

## Почему нельзя просто скачать IPA

В отличие от Android APK, Apple не разрешает обычную установку IPA из браузера.
Для установки на iPhone нужна подпись Apple:

- **App Store / TestFlight** — Apple Developer Program, $99 в год;
- **Ad Hoc** — Apple Developer Program + UDID каждого устройства, максимум 100 устройств;
- **Enterprise** — только для сотрудников организации, публичная раздача запрещена.

Неподписанный IPA не установится на обычный iPhone. Поэтому на сайте для iOS
показывается установка PWA — это полноценная иконка на рабочем столе, полноэкранный
режим и офлайн-оболочка, но без публикации в App Store.

## Сборка нативного приложения на Mac

### 1. Подготовка

Установите:

- macOS и актуальную стабильную Xcode;
- Node.js 20–22;
- CocoaPods (`sudo gem install cocoapods` или `brew install cocoapods`);
- Apple Developer Program и Team ID.

### 2. Сборка веб-части

В приложении нельзя использовать относительный `/api`: WebView откроет
`capacitor://localhost/api`. Поэтому API задаётся при сборке:

```bash
cd frontend
npm ci
VITE_API_BASE_URL=https://virusadk.eu.pythonanywhere.com/api npm run build
npx cap sync ios
```

В PowerShell:

```powershell
cd frontend
$env:VITE_API_BASE_URL="https://virusadk.eu.pythonanywhere.com/api"
npm run build
npx cap sync ios
```

`npx cap sync ios` копирует свежий `dist` в `ios/App/App/public` и выполняет
`pod install`.

### 3. Xcode

```bash
npx cap open ios
```

В Xcode:

1. Выберите проект **App** → target **App** → **Signing & Capabilities**.
2. Укажите свою Team и проверьте Bundle Identifier `by.rybnayalavka.app`.
3. Включите **Automatically manage signing**.
4. Проверьте версию: `1.0.0`, build `1`.
5. Подключите iPhone и запустите на устройстве либо выберите
   **Product → Archive** для TestFlight/App Store.

Для TestFlight:

1. **Product → Archive**.
2. **Distribute App → App Store Connect → Upload**.
3. В App Store Connect заполните карточку, скриншоты, политику
   конфиденциальности и отправьте сборку на проверку.

## Обновления

Для нативного iOS-приложения обновления идут через App Store/TestFlight:

1. Поднимите `MARKETING_VERSION` и `CURRENT_PROJECT_VERSION` в
   `frontend/ios/App/App.xcodeproj/project.pbxproj`.
2. Соберите новую веб-часть и выполните `npx cap sync ios`.
3. Соберите архив и загрузите новую сборку в App Store Connect.

PWA на iPhone обновляется автоматически: сайт показывает баннер
«Доступна новая версия сайта», после нажатия обновляются service worker и кэш.
Для этого `sw.js` и `version.json` должны обновляться вместе с `index.html`.

## CORS

Backend должен разрешать origin iOS WebView:

```env
CORS_ORIGINS=https://virusadk.eu.pythonanywhere.com,https://localhost,http://localhost,capacitor://localhost
```

`https://localhost` нужен Android-приложению, `capacitor://localhost` — iOS.
После изменения `.env` перезагрузите веб-приложение PythonAnywhere.

## Иконка и splash

Файлы:

- `frontend/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png`
- `frontend/ios/App/App/Assets.xcassets/Splash.imageset/splash-2732x2732*.png`

Иконка — 1024×1024 PNG без прозрачности. Splash — 2732×2732 PNG.
Исходник иконки: `frontend/public/icons/icon-512.png`.

## Ограничения

- Сборка IPA невозможна на Windows: нужен macOS/Xcode.
- Прямая ссылка на скачивание IPA, как APK, не подходит для обычных пользователей.
- Для публикации в App Store нужен Apple Developer Program.
- iOS PWA не показывает системный баннер установки: пользователь добавляет
  приложение вручную через Safari → «Поделиться» → «На экран „Домой“».
- В Chrome на iOS установка PWA недоступна — только Safari.

## Чек-лист

- [ ] Проверить `CORS_ORIGINS` с `capacitor://localhost`.
- [ ] Собрать `dist` с production API.
- [ ] Выполнить `npx cap sync ios`.
- [ ] Проверить иконку и splash в Xcode.
- [ ] Указать Team и подпись.
- [ ] Проверить вход, каталог, бронь и историю на iPhone.
- [ ] Загрузить сборку в TestFlight/App Store.
