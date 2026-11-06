import { useEffect, useState, useCallback } from 'react'
import { API_BASE, ApiError } from './api'
import type { PlatformTokenResponse, PlatformUser } from './types'

const TOKEN_KEY = 'tg_platform_token'

export function getPlatformToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setPlatformToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

interface Options {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
}

export async function platformApi<T>(path: string, options: Options = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  const token = getPlatformToken()
  let body: BodyInit | undefined
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }
  if (token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(`${API_BASE}/platform${path}`, {
      method: options.method ?? 'GET',
      headers,
      body,
    })
  } catch {
    throw new ApiError('Нет связи с сервером. Проверьте интернет и попробуйте снова.', 0)
  }

  if (response.status === 401 && token) {
    window.dispatchEvent(new Event('platform:expired'))
  }

  const contentType = response.headers.get('content-type') ?? ''
  const payload = contentType.includes('application/json') ? await response.json() : null
  if (!response.ok) {
    const message =
      typeof payload?.detail === 'string'
        ? payload.detail
        : typeof payload?.detail?.message === 'string'
          ? payload.detail.message
          : 'Что-то пошло не так. Попробуйте ещё раз.'
    throw new ApiError(message, response.status, payload?.errors)
  }
  return payload as T
}

export const platformAuthApi = {
  login: (phone: string, password: string) =>
    platformApi<PlatformTokenResponse>('/auth/login', { method: 'POST', body: { phone, password } }),
  me: () => platformApi<PlatformUser>('/auth/me'),
}

export function usePlatformApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(Boolean(path))
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    if (!path) {
      setLoading(false)
      return
    }
    let alive = true
    setLoading(true)
    setError(null)
    platformApi<T>(path)
      .then((result) => {
        if (alive) setData(result)
      })
      .catch((err) => {
        if (alive) setError(err instanceof Error ? err.message : 'Ошибка загрузки')
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [path, nonce])

  const reload = useCallback(() => setNonce((value) => value + 1), [])
  return { data, loading, error, reload }
}
