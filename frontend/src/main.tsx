import React from 'react'
import ReactDOM from 'react-dom/client'
import { Capacitor } from '@capacitor/core'
import App from './App'
import { captureInstallPrompt } from './lib/pwa'
import './styles.css'
import './styles/landing.css'

if ('scrollRestoration' in history) {
  history.scrollRestoration = 'manual'
}

// Ловим событие установки PWA до монтирования React, иначе оно может потеряться.
captureInstallPrompt()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

// В Android-приложении ассеты уже упакованы в APK. Service worker там только
// мешает обновлению: он может отдать старую версию интерфейса после установки новой APK.
if ('serviceWorker' in navigator && import.meta.env.PROD && !Capacitor.isNativePlatform()) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' }).catch(() => {
      // Приложение продолжает работать без офлайн-кеша.
    })
  })
}
