import { api } from './api'
import type { CartLine } from './types'

const SESSION_KEY = 'rl_cart_session'

/** Стабильный ключ корзины браузера — по нему магазин находит брошенную корзину. */
export function cartSessionKey(): string {
  try {
    const existing = localStorage.getItem(SESSION_KEY)
    if (existing && /^[A-Za-z0-9_-]{8,64}$/.test(existing)) return existing
  } catch {
    // приватный режим — ключ создадим в памяти ниже
  }
  let key = ''
  try {
    key = crypto.randomUUID().replace(/-/g, '')
  } catch {
    key = `c${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`
  }
  try {
    localStorage.setItem(SESSION_KEY, key)
  } catch {
    // без localStorage корзина живёт до перезагрузки
  }
  return key
}

export interface CartContact {
  name?: string
  phone?: string
  email?: string
}

/** Сохраняет корзину на сервере для статистики и напоминаний. */
export function syncCart(lines: CartLine[], contact?: CartContact): Promise<unknown> {
  return api('/cart/sync', {
    method: 'POST',
    auth: true,
    body: {
      session_key: cartSessionKey(),
      items: lines.map((line) => ({ product_id: line.productId, quantity: line.quantity })),
      name: contact?.name?.trim() ?? '',
      phone: contact?.phone?.trim() ?? '',
      email: contact?.email?.trim() ?? '',
    },
  })
}
