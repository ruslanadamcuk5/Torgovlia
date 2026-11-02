export type Platform = 'android' | 'ios' | 'desktop' | 'other'

export const APP_VERSION = __APP_VERSION__
export const APP_BUILD = __APP_BUILD__

const IN_APP_RE = /(FBAN|FBAV|Instagram|Line\/|Telegram|Twitter|MicroMessenger|VKClient)/i

export function detectPlatform(): Platform {
  const ua = navigator.userAgent || ''
  if (/Android/i.test(ua)) return 'android'
  if (/iPhone|iPad|iPod/i.test(ua)) return 'ios'
  if (/Windows|Macintosh|Linux|CrOS/i.test(ua)) return 'desktop'
  return 'other'
}

export function isInAppBrowser(): boolean {
  return IN_APP_RE.test(navigator.userAgent || '')
}

/** Сравнение версий вида 1.2.3. Возвращает <0, 0 или >0. */
export function compareVersions(left: string, right: string): number {
  const a = String(left || '').split('.').map((part) => Number.parseInt(part, 10) || 0)
  const b = String(right || '').split('.').map((part) => Number.parseInt(part, 10) || 0)
  const length = Math.max(a.length, b.length)
  for (let i = 0; i < length; i += 1) {
    const diff = (a[i] || 0) - (b[i] || 0)
    if (diff !== 0) return diff
  }
  return 0
}

/**
 * Ловим beforeinstallprompt как можно раньше, до монтирования React.
 * Иначе событие может произойти до того, как страница /app успеет подписаться.
 */
export function captureInstallPrompt(): void {
  if (typeof window === 'undefined') return

  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault()
    window.__deferredInstallPrompt = event as BeforeInstallPromptEvent
    window.dispatchEvent(new Event('pwa-install-available'))
  })

  window.addEventListener('appinstalled', () => {
    window.__deferredInstallPrompt = undefined
    window.dispatchEvent(new Event('pwa-installed'))
  })
}
