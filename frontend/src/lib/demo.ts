/**
 * Демонстрационный режим одного origin.
 *
 * На бесплатном alwaysdata нельзя подключить wildcard-поддомены, поэтому
 * витрины открываются по пути /shop/<slug>. Выбранный магазин запоминается
 * в sessionStorage, а API добавляет заголовок X-Tenant-Slug. На обычных
 * доменах и поддоменах этот механизм не используется.
 *
 * Именно sessionStorage, а не localStorage: демо открывается в новой вкладке,
 * а localStorage общий для всего origin. Иначе после просмотра демо главная
 * страница платформы начинала показывать витрину магазина.
 */

const DEMO_TENANT_KEY = 'tg_demo_tenant'

// Старая версия хранила магазин в localStorage. Ключ мог «залипнуть» и скрыть
// сайт платформы на `/`, поэтому при загрузке приложения его убираем.
try {
  window.localStorage.removeItem(DEMO_TENANT_KEY)
} catch {
  // Приватный режим или отключённое хранилище — демо просто не запомнится.
}

function demoStorage(): Storage | null {
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

export function getDemoTenant(): string | null {
  const value = demoStorage()?.getItem(DEMO_TENANT_KEY)
  return value && /^[a-z0-9-]+$/.test(value) ? value : null
}

export function setDemoTenant(slug: string): void {
  demoStorage()?.setItem(DEMO_TENANT_KEY, slug)
}

export function clearDemoTenant(): void {
  try {
    window.sessionStorage.removeItem(DEMO_TENANT_KEY)
    window.localStorage.removeItem(DEMO_TENANT_KEY)
  } catch {
    // Ничего не делаем: демо и так не сохранится.
  }
}
