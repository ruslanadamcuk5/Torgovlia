/**
 * Демонстрационный режим одного origin.
 *
 * На бесплатном alwaysdata нельзя подключить wildcard-поддомены, поэтому
 * витрины открываются по пути /shop/<slug>. Выбранный магазин запоминается
 * в localStorage, а API добавляет заголовок X-Tenant-Slug. На обычных
 * доменах и поддоменах этот механизм не используется.
 */

const DEMO_TENANT_KEY = 'tg_demo_tenant'

export function getDemoTenant(): string | null {
  const value = localStorage.getItem(DEMO_TENANT_KEY)
  return value && /^[a-z0-9-]+$/.test(value) ? value : null
}

export function setDemoTenant(slug: string): void {
  localStorage.setItem(DEMO_TENANT_KEY, slug)
}

export function clearDemoTenant(): void {
  localStorage.removeItem(DEMO_TENANT_KEY)
}
