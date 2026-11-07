/** Хост платформы: на нём показываем сайт продаж, а не витрину магазина. */
export function isPlatformHost(): boolean {
  const configured = (import.meta.env.VITE_PLATFORM_HOSTS as string | undefined)
    ?.split(',')
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean)
  const hosts = configured?.length ? configured : ['localhost', '127.0.0.1']
  return hosts.includes(window.location.hostname.toLowerCase())
}

/** Полный адрес магазина с сохранением dev-порта. */
export function siteUrl(host: string, path = '/'): string {
  const port = window.location.port
  const portPart = port && port !== '80' && port !== '443' ? `:${port}` : ''
  return `${window.location.protocol}//${host}${portPart}${path}`
}

/**
 * Демо-витрины на одном origin (/shop/<slug>).
 * Включается только при сборке для стенда без wildcard-поддоменов.
 */
export const demoStorefrontsEnabled = import.meta.env.VITE_DEMO_STOREFRONTS === '1'

/** Ссылка на витрину: обычный домен магазина или демо-путь. */
export function storefrontUrl(slug: string, host: string, path = '/'): string {
  if (!demoStorefrontsEnabled) return siteUrl(host, path)
  const suffix = path === '/' ? '' : path.startsWith('/') ? path : `/${path}`
  return `${window.location.origin}/shop/${slug}${suffix}`
}
