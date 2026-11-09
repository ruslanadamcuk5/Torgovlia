import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { useSite } from '../store/SettingsContext'

declare global {
  interface Window {
    dataLayer?: unknown[]
    gtag?: (...args: unknown[]) => void
    ym?: (...args: unknown[]) => void
    fbq?: ((...args: unknown[]) => void) & { queue?: unknown[] }
  }
}

const SKIP_PREFIXES = ['/admin', '/platform', '/seller', '/status', '/shop/']

function addScript(id: string, src: string, onload?: () => void) {
  if (document.getElementById(id)) {
    onload?.()
    return
  }
  const script = document.createElement('script')
  script.id = id
  script.async = true
  script.src = src
  if (onload) script.addEventListener('load', onload, { once: true })
  document.head.appendChild(script)
}

/**
 * Счётчики аналитики магазина. Подключаются только на витрине и только
 * если владелец указал идентификаторы в «Настройки → SEO и аналитика».
 */
export function Analytics() {
  const { site } = useSite()
  const location = useLocation()
  const s = site?.settings
  const yandex = (s?.analytics_yandex ?? '').trim()
  const google = (s?.analytics_google ?? '').trim()
  const pixel = (s?.analytics_meta_pixel ?? '').trim()
  const enabled = Boolean(s?.seo_indexing || yandex || google || pixel)

  useEffect(() => {
    if (!enabled) return
    if (SKIP_PREFIXES.some((prefix) => location.pathname.startsWith(prefix))) return

    if (yandex) {
      addScript('ym-tag', 'https://mc.yandex.ru/metrika/tag.js', () => {
        window.ym?.(Number(yandex), 'init', {
          clickmap: true,
          trackLinks: true,
          accurateTrackBounce: true,
          webvisor: true,
        })
      })
    }

    if (google) {
      addScript('ga4-tag', `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(google)}`)
      window.dataLayer = window.dataLayer || []
      window.gtag =
        window.gtag ||
        function gtag(...args: unknown[]) {
          window.dataLayer?.push(args)
        }
      window.gtag('js', new Date())
      window.gtag('config', google)
    }

    if (pixel) {
      if (!window.fbq) {
        const fbq = function (...args: unknown[]) {
          ;(fbq.queue = fbq.queue || []).push(args)
        } as Window['fbq'] & { queue?: unknown[] }
        window.fbq = fbq
      }
      addScript('fb-pixel', 'https://connect.facebook.net/en_US/fbevents.js', () => {
        window.fbq?.('init', pixel)
        window.fbq?.('track', 'PageView')
      })
    }
  }, [enabled, yandex, google, pixel, location.pathname])

  return null
}
