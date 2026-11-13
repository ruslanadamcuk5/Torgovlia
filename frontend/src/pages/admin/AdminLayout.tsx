import { Fragment, useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../store/AuthContext'
import { useSite } from '../../store/SettingsContext'
import { useApi } from '../../lib/useApi'
import { assetUrl } from '../../lib/api'
import { Icon, type IconName } from '../../components/icons'
import type { Stats } from '../../lib/types'
import { useScrollReveal } from '../../lib/reveal'

const NAV: { to: string; label: string; icon: IconName; group: string; end?: boolean }[] = [
  { to: '/admin', label: 'Обзор', icon: 'dashboard', group: 'Продажи', end: true },
  { to: '/admin/orders', label: 'Заказы', icon: 'list', group: 'Продажи' },
  { to: '/admin/reports', label: 'Отчёты', icon: 'chart', group: 'Продажи' },
  { to: '/admin/catalog', label: 'Каталог', icon: 'grid', group: 'Каталог и склад' },
  { to: '/admin/inventory', label: 'Склад', icon: 'box', group: 'Каталог и склад' },
  { to: '/admin/suppliers', label: 'Поставщики', icon: 'users', group: 'Каталог и склад' },
  { to: '/admin/promotions', label: 'Акции', icon: 'percent', group: 'Каталог и склад' },
  { to: '/admin/promo-codes', label: 'Промокоды', icon: 'tag', group: 'Каталог и склад' },
  { to: '/admin/reviews', label: 'Отзывы', icon: 'star', group: 'Каталог и склад' },
  { to: '/admin/delivery', label: 'Доставка', icon: 'car', group: 'Каталог и склад' },
  { to: '/admin/barcodes', label: 'Штрихкоды', icon: 'tag', group: 'Каталог и склад' },
  { to: '/admin/price-tags', label: 'Ценники', icon: 'print', group: 'Каталог и склад' },
  { to: '/admin/imports', label: 'Импорт прайсов', icon: 'upload', group: 'Каталог и склад' },
  { to: '/admin/crm', label: 'Клиенты', icon: 'users', group: 'Клиенты' },
  { to: '/admin/loyalty', label: 'Бонусы', icon: 'gift', group: 'Клиенты' },
  { to: '/admin/chat', label: 'Чат', icon: 'mail', group: 'Клиенты' },
  { to: '/admin/tasks', label: 'Задачи', icon: 'check', group: 'Клиенты' },
  { to: '/admin/campaigns', label: 'Рассылки', icon: 'send', group: 'Клиенты' },
  { to: '/admin/carts', label: 'Брошенные корзины', icon: 'cart', group: 'Клиенты' },
  { to: '/admin/upsells', label: 'Допродажи', icon: 'tag', group: 'Клиенты' },
  { to: '/admin/certificates', label: 'Сертификаты', icon: 'gift', group: 'Клиенты' },
  { to: '/admin/subscriptions', label: 'Регулярные заказы', icon: 'refresh', group: 'Клиенты' },
  { to: '/admin/services', label: 'Сервисы', icon: 'sparkles', group: 'Платформа' },
  { to: '/admin/billing', label: 'Оплата', icon: 'wallet', group: 'Платформа' },
  { to: '/admin/users', label: 'Пользователи', icon: 'users', group: 'Платформа' },
  { to: '/admin/settings', label: 'Настройки', icon: 'settings', group: 'Платформа' },
  { to: '/admin/notifications', label: 'Уведомления', icon: 'bell', group: 'Платформа' },
  { to: '/admin/qr', label: 'QR-коды', icon: 'qr', group: 'Платформа' },
]

const TITLES: Record<string, string> = {
  '/admin': 'Обзор магазина',
  '/admin/orders': 'Заказы покупателей',
  '/admin/appointments': 'Записи на услуги',
  '/admin/specialists': 'Специалисты и график',
  '/admin/reports': 'Отчёты и экспорт',
  '/admin/catalog': 'Управление каталогом',
  '/admin/inventory': 'Склад и остатки',
  '/admin/suppliers': 'Поставщики и закупки',
  '/admin/promotions': 'Акции и товар дня',
  '/admin/promo-codes': 'Промокоды и скидки',
  '/admin/reviews': 'Отзывы покупателей',
  '/admin/delivery': 'Доставка и зоны',
  '/admin/services': 'Сервисы магазина',
  '/admin/billing': 'Тариф и оплата',
  '/admin/users': 'Пользователи и роли',
  '/admin/settings': 'Настройки сайта',
  '/admin/notifications': 'Уведомления о заказах',
  '/admin/qr': 'QR-коды',
  '/admin/price-tags': 'Ценники и этикетки',
  '/admin/barcodes': 'Штрихкоды и этикетки',
  '/admin/imports': 'Импорт прайсов',
  '/admin/campaigns': 'Рассылки и сегменты',
  '/admin/carts': 'Брошенные корзины',
  '/admin/upsells': 'Допродажи',
  '/admin/loyalty': 'Бонусная программа',
  '/admin/crm': 'Клиенты и сегменты',
  '/admin/chat': 'Чат с покупателем',
  '/admin/tasks': 'Задачи сотрудникам',
  '/admin/certificates': 'Подарочные сертификаты',
  '/admin/subscriptions': 'Регулярные заказы',
}

export default function AdminLayout() {
  const { user, logout, impersonation } = useAuth()
  const { site } = useSite()
  const location = useLocation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const { data: stats } = useApi<Stats>('/admin/stats')
  useScrollReveal()

  useEffect(() => setOpen(false), [location.pathname])

  if (!user || !site) return null
  const s = site.settings
  const today = site.today
  const serviceMode = site.tenant?.business_type === 'services'
  const goodsOnly = new Set([
    '/admin/inventory',
    '/admin/suppliers',
    '/admin/delivery',
    '/admin/carts',
    '/admin/subscriptions',
  ])
  const visibleNav = serviceMode ? NAV.filter((item) => !goodsOnly.has(item.to)) : NAV
  const navItems = serviceMode
    ? [
      visibleNav[0],
      { to: '/admin/appointments', label: 'Записи', icon: 'calendar' as IconName, group: 'Продажи' },
      { to: '/admin/specialists', label: 'Специалисты', icon: 'users' as IconName, group: 'Продажи' },
      ...visibleNav.slice(1),
    ]
    : visibleNav
  const pageTitle = TITLES[location.pathname]
    ?? (location.pathname.startsWith('/admin/services/') ? 'Сервис магазина' : 'Админ-панель')

  return (
    <div className="admin-shell">
      <aside className={`admin-sidebar ${open ? 'is-open' : ''}`}>
        <Link to="/admin" className="admin-brand">
          <img src={assetUrl(s.logo_url)} alt="" width={40} height={40} />
          <span><strong>{s.brand_name}</strong><small>Админ-панель</small></span>
        </Link>

        <div className="admin-place">
          <Icon name="pin" size={16} />
          <div>
            <strong>{s.city}</strong>
            <span>{s.market_name} · {s.pavilion}</span>
          </div>
        </div>

        <nav className="admin-nav">
          {navItems.map((item, index) => (
            <Fragment key={item.to}>
              {(index === 0 || navItems[index - 1].group !== item.group) && (
                <span className="admin-nav__group">{item.group}</span>
              )}
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) => (isActive ? 'is-active' : '')}
              >
                <Icon name={item.icon} size={19} />
                <span>{item.label}</span>
                {item.to === '/admin/orders' && (stats?.orders_new ?? 0) > 0 && <b className="admin-nav__badge">{stats?.orders_new}</b>}
              </NavLink>
            </Fragment>
          ))}
        </nav>

        <div className="admin-sidebar__foot">
          <Link to="/" className="admin-side-link"><Icon name="external" size={17} /> Открыть сайт</Link>
          <Link to="/seller" className="admin-side-link"><Icon name="smartphone" size={17} /> Режим продавца</Link>
          <div className="admin-user">
            <span className="avatar avatar--sm">{user.full_name.slice(0, 1).toUpperCase()}</span>
            <div><strong>{user.full_name}</strong><span>{user.role === 'admin' ? 'Администратор' : 'Продавец'}</span></div>
            <button type="button" className="icon-btn" aria-label="Выйти" onClick={() => { logout(); navigate('/') }}>
              <Icon name="logout" size={17} />
            </button>
          </div>
        </div>
      </aside>

      {open && <button type="button" className="admin-overlay" aria-label="Закрыть меню" onClick={() => setOpen(false)} />}

      <div className="admin-main">
        {impersonation && (
          <div className="impersonation-banner">
            <Icon name="alert" size={17} />
            <span>
              <strong>Режим платформы.</strong> Вы вошли как {user.full_name} по причине:
              {' '}{impersonation.imp_reason || 'без комментария'}. Действия записываются в аудит.
            </span>
            <button type="button" className="btn btn--sm btn--ghost" onClick={() => { logout(); navigate('/') }}>
              Выйти
            </button>
          </div>
        )}
        <header className="admin-topbar">
          <button type="button" className="icon-btn admin-burger" onClick={() => setOpen(true)} aria-label="Меню">
            <Icon name="menu" size={22} />
          </button>
          <div className="admin-topbar__title">
            <h1>{pageTitle}</h1>
            <span className="admin-topbar__status">
              <span className={`dot ${today.is_closed ? 'dot--muted' : ''}`} />
              {today.is_closed ? 'Магазин закрыт' : `Открыто до ${today.close}`}
            </span>
          </div>
          <div className="admin-topbar__actions">
            <Link to="/catalog" className="btn btn--sm btn--ghost"><Icon name="eye" size={16} /> <span>Сайт</span></Link>
            <Link to="/admin/orders" className="admin-topbar__bell">
              <Icon name="bell" size={19} />
              {(stats?.orders_new ?? 0) > 0 && <b>{stats?.orders_new}</b>}
            </Link>
          </div>
        </header>

        <div className="admin-content">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
