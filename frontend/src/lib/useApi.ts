import { useCallback, useEffect, useState } from 'react'
import { api } from './api'

export function useApi<T>(path: string | null, auth = true) {
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
    api<T>(path, { auth })
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
  }, [path, auth, nonce])

  const reload = useCallback(() => setNonce((value) => value + 1), [])
  return { data, loading, error, reload }
}
