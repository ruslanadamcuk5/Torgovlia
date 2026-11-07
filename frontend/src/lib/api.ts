import { getDemoTenant } from './demo'
import { isPlatformHost } from './host'

const TOKEN_KEY = 'rl_token'

const RAW_API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim()

/** База API: относительная для сайта, абсолютная для Android/Capacitor. */
export const API_BASE = (RAW_API_BASE || '/api').replace(/\/$/, '')

/** Origin backend, если приложение собрано для Android и API вынесен на домен. */
export const API_ORIGIN = /^https?:\/\//i.test(API_BASE)
  ? new URL(API_BASE).origin
  : ''

/**
 * Приводит серверный путь (фото, QR, вложение) к адресу, доступному и в Android-приложении.
 * Локальные файлы фронтенда (/assets/...) не трогаем — они упакованы в APK.
 */
export function assetUrl(value?: string | null): string {
  if (!value) return ''
  if (/^(https?:|data:|blob:|capacitor:|file:)/i.test(value)) return value
  if (API_ORIGIN && value.startsWith('/') && !value.startsWith('/assets/')) return `${API_ORIGIN}${value}`
  return value
}

export class ApiError extends Error {
  status: number
  errors?: { field: string; message: string }[]

  constructor(message: string, status: number, errors?: { field: string; message: string }[]) {
    super(message)
    this.status = status
    this.errors = errors
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  auth?: boolean
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  const token = getToken()

  let body: BodyInit | undefined
  if (options.body instanceof FormData) {
    body = options.body
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }
  if (token && options.auth !== false) headers.Authorization = `Bearer ${token}`

  // Демо-стенд: витрина на том же origin, арендатор выбирается заголовком.
  const demoTenant = getDemoTenant()
  if (
    demoTenant
    && isPlatformHost()
    && !path.startsWith('/platform')
    && !path.startsWith('/signup')
  ) {
    headers['X-Tenant-Slug'] = demoTenant
  }

  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, { method: options.method ?? 'GET', headers, body })
  } catch {
    throw new ApiError('Нет связи с сервером. Проверьте интернет и попробуйте снова.', 0)
  }

  if (response.status === 401 && token) {
    window.dispatchEvent(new Event('auth:expired'))
  }

  const contentType = response.headers.get('content-type') ?? ''
  const payload = contentType.includes('application/json') ? await response.json() : null

  if (!response.ok) {
    const message =
      typeof payload?.detail === 'string'
        ? payload.detail
        : typeof payload?.detail?.message === 'string'
          ? payload.detail.message
          : Array.isArray(payload?.detail)
            ? 'Проверьте заполнение полей'
            : 'Что-то пошло не так. Попробуйте ещё раз.'
    throw new ApiError(message, response.status, payload?.errors)
  }
  return payload as T
}

export async function uploadImage(file: File, endpoint = '/admin/uploads'): Promise<{ url: string; filename: string; size: number }> {
  const data = new FormData()
  data.append('file', file)
  return api(endpoint, { method: 'POST', body: data })
}

export const authApi = {
  requestCode: (phone: string, purpose: 'register' | 'login' | 'order' | 'reset') =>
    api<import('./types').PhoneRequest>('/auth/phone/request', { method: 'POST', body: { phone, purpose }, auth: false }),
  confirmCode: (verification_id: string, code: string) =>
    api<import('./types').PhoneConfirm>('/auth/phone/confirm', { method: 'POST', body: { verification_id, code }, auth: false }),
  register: (data: { phone_token: string; password: string; full_name: string; email?: string; consent_personal_data: boolean }) =>
    api<import('./types').TokenResponse>('/auth/register', { method: 'POST', body: data, auth: false }),
  login: (phone: string, password: string) =>
    api<import('./types').TokenResponse>('/auth/login', { method: 'POST', body: { phone, password }, auth: false }),
  loginByPhone: (phone_token: string) =>
    api<import('./types').TokenResponse>('/auth/login/phone', { method: 'POST', body: { phone_token }, auth: false }),
  resetPassword: (phone_token: string, password: string) =>
    api<{ ok: boolean; message: string }>('/auth/password/reset', { method: 'POST', body: { phone_token, password }, auth: false }),
  me: () => api<import('./types').User>('/auth/me'),
  updateProfile: (data: { full_name?: string; email?: string }) =>
    api<import('./types').User>('/auth/me', { method: 'PATCH', body: data }),
  changePassword: (current_password: string, new_password: string) =>
    api<{ ok: boolean; message: string }>('/auth/password/change', { method: 'POST', body: { current_password, new_password } }),
  deleteAccount: (password: string, confirmation: string) =>
    api<{ ok: boolean; message: string }>('/account/delete', {
      method: 'POST',
      body: { password, confirmation },
    }),
}
