import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../lib/api'
import { demoStorefrontsEnabled } from '../lib/host'
import { getDemoTenant } from '../lib/demo'
import type { SiteInfo } from '../lib/types'

interface SettingsContextValue {
  site: SiteInfo | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

const SettingsContext = createContext<SettingsContextValue | null>(null)

function absoluteUrl(path: string): string {
  if (!path) return ''
  return /^https?:/i.test(path) ? path : new URL(path, window.location.origin).toString()
}

/** Публичный адрес витрины: свой домен или демо-путь /shop/<slug>. */
export function storefrontBase(): string {
  const demo = getDemoTenant()
  if (demoStorefrontsEnabled && demo) return `${window.location.origin}/shop/${demo}`
  return window.location.origin
}

function upsertMeta(attr: 'name' | 'property', key: string, content: string) {
  if (!content) return
  let tag = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${key}"]`)
  if (!tag) {
    tag = document.createElement('meta')
    tag.setAttribute(attr, key)
    document.head.appendChild(tag)
  }
  tag.setAttribute('content', content)
}

function upsertLink(rel: string, href: string) {
  if (!href) return
  let tag = document.head.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`)
  if (!tag) {
    tag = document.createElement('link')
    tag.setAttribute('rel', rel)
    document.head.appendChild(tag)
  }
  tag.setAttribute('href', href)
}

function upsertJsonLd(id: string, data: unknown) {
  let tag = document.getElementById(id) as HTMLScriptElement | null
  if (!tag) {
    tag = document.createElement('script')
    tag.id = id
    tag.type = 'application/ld+json'
    document.head.appendChild(tag)
  }
  tag.textContent = JSON.stringify(data)
}

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
    const s = site.settings
    const base = storefrontBase()
    const title = s.seo_title || `${s.brand_name} — ${s.city}`
    const image = absoluteUrl(s.seo_og_image_url || s.logo_url)

    document.title = title
    upsertMeta('name', 'description', s.seo_description)
    upsertMeta('name', 'keywords', s.seo_keywords)
    upsertMeta('name', 'robots', s.seo_indexing ? 'index, follow' : 'noindex, nofollow')
    upsertMeta('property', 'og:site_name', s.brand_name)
    upsertMeta('property', 'og:title', title)
    upsertMeta('property', 'og:description', s.seo_description)
    upsertMeta('property', 'og:type', 'website')
    upsertMeta('property', 'og:url', base)
    upsertMeta('property', 'og:image', image)
    upsertMeta('property', 'og:locale', 'ru_BY')
    upsertMeta('name', 'twitter:card', image ? 'summary_large_image' : 'summary')
    upsertMeta('name', 'twitter:title', title)
    upsertMeta('name', 'twitter:description', s.seo_description)
    upsertMeta('name', 'twitter:image', image)
    upsertLink('canonical', `${base}${window.location.pathname === '/' ? '/' : window.location.pathname}`)

    const closing = s.working_hours
      .filter((day) => !day.closed)
      .map((day) => `${['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'][day.weekday]} ${day.open}-${day.close}`)
    upsertJsonLd('ld-store', {
      '@context': 'https://schema.org',
      '@type': 'Store',
      name: s.brand_name,
      description: s.seo_description || s.tagline,
      url: base,
      image,
      logo: absoluteUrl(s.logo_url),
      telephone: s.phone,
      email: s.email,
      address: {
        '@type': 'PostalAddress',
        streetAddress: s.address,
        addressLocality: s.city,
        addressCountry: 'BY',
      },
      openingHours: closing,
      priceRange: 'BYN',
    })
  }, [site])

  const value = useMemo(() => ({ site, loading, error, refresh }), [site, loading, error, refresh])
  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
}

export function useSite(): SettingsContextValue {
  const context = useContext(SettingsContext)
  if (!context) throw new Error('useSite must be used within SettingsProvider')
  return context
}
