import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../lib/api'
import type { SiteInfo } from '../lib/types'

interface SettingsContextValue {
  site: SiteInfo | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

const SettingsContext = createContext<SettingsContextValue | null>(null)

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [site, setSite] = useState<SiteInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api<SiteInfo>('/site', { auth: false })
      setSite(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить данные сайта')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (!site) return
    document.title = site.settings.seo_title || `${site.settings.brand_name} — ${site.settings.city}`
    const description = document.querySelector('meta[name="description"]')
    if (description) description.setAttribute('content', site.settings.seo_description)
  }, [site])

  const value = useMemo(() => ({ site, loading, error, refresh }), [site, loading, error, refresh])
  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
}

export function useSite(): SettingsContextValue {
  const context = useContext(SettingsContext)
  if (!context) throw new Error('useSite must be used within SettingsProvider')
  return context
}
