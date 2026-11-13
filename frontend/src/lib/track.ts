import { API_BASE } from './api'

export type TrackKind =
  | 'visit'
  | 'demo_storefront'
  | 'demo_service'
  | 'demo_admin'
  | 'signup_start'
  | 'signup_created'
  | 'platform_login'

const SESSION_KEY = 'tg_visit_key'
let sentVisit = false

function sessionKey(): string {
  try {
    const existing = localStorage.getItem(SESSION_KEY)
    if (existing) return existing
    const value =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID().replace(/-/g, '')
        : `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`
    localStorage.setItem(SESSION_KEY, value)
    return value
  } catch {
    return ''
  }
}

/**
 * Отправляет обезличенное событие интереса к платформе.
 * Ничего не ломает, если сеть или хранилище недоступны.
 */
export function track(kind: TrackKind, extra: { detail?: string; source?: string; campaign?: string } = {}) {
  try {
    if (kind === 'visit') {
      if (sentVisit) return
      sentVisit = true
    }
    const params = new URLSearchParams(window.location.search)
    const payload = {
      kind,
      path: window.location.pathname,
      referrer: document.referrer || '',
      session_key: sessionKey(),
      source: extra.source ?? (params.get('utm_source') ?? ''),
      campaign: extra.campaign ?? (params.get('utm_campaign') ?? ''),
      detail: extra.detail ?? '',
    }
    void fetch(`${API_BASE}/platform/track`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => undefined)
  } catch {
    // Телеметрия не должна мешать работе сайта.
  }
}
