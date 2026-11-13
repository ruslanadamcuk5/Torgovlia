import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

/**
 * Мягкое появление блоков при прокрутке на всех страницах витрины и админок.
 * Классы навешиваются автоматически, поэтому новые разделы не нужно
 * размечать вручную. Уважает prefers-reduced-motion и не трогает модальные окна.
 */
const TARGETS = [
  '.hero__content > *',
  '.hero__visual',
  '.advantage',
  '.section > .container > *',
  '.product-card',
  '.service-card',
  '.daily-deal',
  '.banner-card',
  '.catalog-layout > *',
  '.product-hero > *',
  '.booking-layout > *',
  '.booking-wizard > *',
  '.cart-layout > *',
  '.checkout-layout > *',
  '.account-grid > *',
  '.auth-shell',
  '.contacts-card',
  '.article-card',
  '.panel',
  '.stat-card',
  '.admin-welcome',
  '.admin-page > *',
  '.admin-dashboard-grid > *',
  '.seller-main > *',
  '.seller-order',
  '.seller-stat',
  '.seller-product',
  '.platform-page > *',
  '.platform-stats > *',
  '.data-table tbody tr',
  '.platform-table tbody tr',
].join(',')

export function useScrollReveal(): void {
  const { pathname } = useLocation()

  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined' || typeof MutationObserver === 'undefined') return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const root = document.querySelector<HTMLElement>('main, .admin-content, .seller-main')
    if (!root) return

    root.classList.add('ui-anim')
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue
          entry.target.classList.add('is-in')
          observer.unobserve(entry.target)
        }
      },
      { rootMargin: '0px 0px -6% 0px', threshold: 0.06 },
    )

    let frame = 0
    const scan = () => {
      frame = 0
      const nodes = root.querySelectorAll<HTMLElement>(TARGETS)
      let index = 0
      nodes.forEach((element) => {
        if (element.dataset.uiReveal) return
        if (element.closest('.modal, .toasts, .admin-topbar, [data-no-reveal]')) return
        element.dataset.uiReveal = '1'
        element.classList.add('ui-reveal')
        element.style.setProperty('--ui-delay', `${Math.min(index % 8, 7) * 55}ms`)
        observer.observe(element)
        index += 1
      })
    }
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(scan)
    }
    scan()
    const mutations = new MutationObserver(schedule)
    mutations.observe(root, { childList: true, subtree: true })

    return () => {
      cancelAnimationFrame(frame)
      mutations.disconnect()
      observer.disconnect()
      root.classList.remove('ui-anim')
    }
  }, [pathname])
}
