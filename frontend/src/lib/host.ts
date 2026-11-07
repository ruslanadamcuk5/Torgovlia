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
