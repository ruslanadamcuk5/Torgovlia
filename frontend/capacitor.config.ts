import type { CapacitorConfig } from '@capacitor/cli'

/**
 * Android-приложение покупателя.
 *
 * Перед сборкой APK/App Bundle обязательно задайте адрес production API:
 *   VITE_API_BASE_URL=https://rybnaya-lavka.by/api npm run cap:sync
 *
 * Для локальной отладки на телефоне в той же Wi-Fi сети:
 *   VITE_API_BASE_URL=http://192.168.1.10:8000/api npm run cap:sync
 */
const allowHttpForDebug = process.env.CAPACITOR_ALLOW_HTTP === 'true'

const config: CapacitorConfig = {
  appId: 'by.rybnayalavka.app',
  appName: 'Рыбная лавка',
  webDir: 'dist',
  server: {
    androidScheme: 'https',
  },
  android: {
    // true — только для локальной отладки через HTTP-туннель.
    allowMixedContent: allowHttpForDebug,
    captureInput: true,
    webContentsDebuggingEnabled: allowHttpForDebug,
  },
}

export default config
