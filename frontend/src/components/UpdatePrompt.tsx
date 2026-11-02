import { useEffect, useRef, useState } from 'react'
import { Capacitor } from '@capacitor/core'
import { API_BASE, assetUrl } from '../lib/api'
import { APP_BUILD, APP_VERSION, compareVersions } from '../lib/pwa'

type UpdateKind = 'pwa' | 'web' | 'native'

interface UpdateInfo {
  kind: UpdateKind
  title: string
  text: string
  url?: string
}

export default function UpdatePrompt() {
  const [update, setUpdate] = useState<UpdateInfo | null>(null)
  const dismissedRef = useRef(false)
  const waitingWorkerRef = useRef<ServiceWorker | null>(null)
  const shouldReloadRef = useRef(false)

  const show = (next: UpdateInfo) => {
    if (dismissedRef.current) return
    setUpdate((current) => current || next)
  }

  useEffect(() => {
    if (Capacitor.isNativePlatform()) {
      let stopped = false
      const checkNativeUpdate = async () => {
        if (stopped) return
        try {
          const response = await fetch(`${API_BASE}/site`, { cache: 'no-store' })
          if (!response.ok) return
          const data = (await response.json()) as {
            settings?: { android_app_version?: string; android_apk_url?: string; app_install_url?: string }
          }
          const settings = data.settings || {}
          const serverVersion = settings.android_app_version || ''
          if (!serverVersion || compareVersions(serverVersion, APP_VERSION) <= 0) return
          show({
            kind: 'native',
            title: 'Доступна новая версия приложения',
            text: `Версия ${serverVersion}. Скачайте обновление и установите поверх текущей — данные и вход сохранятся.`,
            url: settings.android_apk_url || settings.app_install_url || undefined,
          })
        } catch {
          // Нет сети — повторим при следующем открытии/проверке.
        }
      }
      void checkNativeUpdate()
      const timer = window.setInterval(checkNativeUpdate, 30 * 60 * 1000)
      const onVisible = () => {
        if (document.visibilityState === 'visible') void checkNativeUpdate()
      }
      document.addEventListener('visibilitychange', onVisible)
      return () => {
        stopped = true
        window.clearInterval(timer)
        document.removeEventListener('visibilitychange', onVisible)
      }
    }

    let stopped = false

    const checkWebVersion = async () => {
      if (stopped) return
      try {
        const response = await fetch(`/version.json?t=${Date.now()}`, { cache: 'no-store' })
        if (!response.ok) return
        const data = (await response.json()) as { build?: string; version?: string }
        if (!data.build || data.build === APP_BUILD) return
        show({
          kind: 'web',
          title: 'Доступна новая версия сайта',
          text: 'Мы обновили каталог и приложение. Перезагрузите страницу, чтобы получить свежую версию.',
        })
      } catch {
        // Игнорируем: при следующей проверке попробуем снова.
      }
    }

    void checkWebVersion()
    const versionTimer = window.setInterval(checkWebVersion, 5 * 60 * 1000)
    const onVisible = () => {
      if (document.visibilityState === 'visible') void checkWebVersion()
    }
    document.addEventListener('visibilitychange', onVisible)

    const onControllerChange = () => {
      if (shouldReloadRef.current) window.location.reload()
    }

    const watchRegistration = (registration: ServiceWorkerRegistration) => {
      if (registration.waiting && navigator.serviceWorker.controller) {
        waitingWorkerRef.current = registration.waiting
        show({
          kind: 'pwa',
          title: 'Приложение обновлено',
          text: 'Новая версия уже загружена. Нажмите «Обновить», чтобы открыть её.',
        })
      }

      registration.addEventListener('updatefound', () => {
        const worker = registration.installing
        if (!worker) return
        worker.addEventListener('statechange', () => {
          if (worker.state !== 'installed' || !navigator.serviceWorker.controller) return
          waitingWorkerRef.current = worker
          show({
            kind: 'pwa',
            title: 'Приложение обновлено',
            text: 'Новая версия уже загружена. Нажмите «Обновить», чтобы открыть её.',
          })
        })
      })
    }

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.addEventListener('controllerchange', onControllerChange)
      navigator.serviceWorker
        .getRegistration()
        .then((registration) => {
          if (registration) watchRegistration(registration)
        })
        .catch(() => undefined)
    }

    const refreshServiceWorker = () => {
      navigator.serviceWorker
        ?.getRegistration()
        .then((registration) => registration?.update())
        .catch(() => undefined)
    }
    const swTimer = window.setInterval(refreshServiceWorker, 15 * 60 * 1000)
    const onServiceWorkerVisible = () => {
      if (document.visibilityState === 'visible') refreshServiceWorker()
    }
    document.addEventListener('visibilitychange', onServiceWorkerVisible)

    return () => {
      stopped = true
      window.clearInterval(versionTimer)
      window.clearInterval(swTimer)
      document.removeEventListener('visibilitychange', onVisible)
      document.removeEventListener('visibilitychange', onServiceWorkerVisible)
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.removeEventListener('controllerchange', onControllerChange)
      }
    }
  }, [])

  const dismiss = () => {
    dismissedRef.current = true
    setUpdate(null)
  }

  const applyPwaUpdate = () => {
    const worker = waitingWorkerRef.current
    if (!worker) {
      window.location.reload()
      return
    }
    shouldReloadRef.current = true
    worker.postMessage({ type: 'SKIP_WAITING' })
    // Страховка, если controllerchange не придёт (например, Safari).
    window.setTimeout(() => window.location.reload(), 2500)
  }

  if (!update) return null

  return (
    <div className="update-toast" role="status" aria-live="polite">
      <div className="update-toast__text">
        <strong>{update.title}</strong>
        <span>{update.text}</span>
      </div>
      {update.kind === 'native' && update.url && (
        <a className="btn btn--gold btn--sm" href={assetUrl(update.url)} target="_blank" rel="noopener noreferrer">
          Скачать
        </a>
      )}
      {update.kind === 'web' && (
        <button type="button" className="btn btn--gold btn--sm" onClick={() => window.location.reload()}>
          Обновить
        </button>
      )}
      {update.kind === 'pwa' && (
        <button type="button" className="btn btn--gold btn--sm" onClick={applyPwaUpdate}>
          Обновить
        </button>
      )}
      <button type="button" className="update-toast__close" onClick={dismiss} aria-label="Закрыть уведомление">
        ×
      </button>
    </div>
  )
}
