import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../store/AuthContext'
import { useSite } from '../../store/SettingsContext'
import { useApi } from '../../lib/useApi'
import { assetUrl } from '../../lib/api'
import { Icon, type IconName } from '../../components/icons'
import type { Stats } from '../../lib/types'

const NAV: { to: string; label: string; icon: IconName; end?: boolean }[] = [
  { to: '/admin', label: 'Обзор', icon: 'dashboard', end: true },
  { to: '/admin/orders', label: 'Брони', icon: 'list' },
  { to: '/admin/catalog', label: 'Каталог', icon: 'fish' },
  { to: '/admin/promotions', label: 'Акции', icon: 'percent' },
  { to: '/admin/promo-codes', label: 'Промокоды', icon: 'tag' },
  { to: '/admin/services', label: 'Сервисы', icon: 'sparkles' },
  { to: '/admin/billing', label: 'Оплата', icon: 'wallet' },
  { to: '/admin/users', label: 'Пользователи', icon: 'users' },
  { to: '/admin/settings', label: 'Настройки', icon: 'settings' },
  { to: '/admin/qr', label: 'QR-коды', icon: 'qr' },
]

const TITLES: Record<string, string> = {
  '/admin': 'Обзор магазина',
  '/admin/orders': 'Брони покупателей',
  '/admin/catalog': 'Управление каталогом',
  '/admin/promotions': 'Акции и товар дня',
  '/admin/promo-codes': 'Промокоды и скидки',
  '/admin/services': 'Сервисы магазина',
  '/admin/billing': 'Тариф и оплата',
  '/admin/users': 'Пользователи и роли',
  '/admin/settings': 'Настройки сайта',
  '/admin/qr': 'QR-коды',
}

export default function AdminLayout() {
  const { user, logout, impersonation } = useAuth()
  const { site } = useSite()
  const location = useLocation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const { data: stats } = useApi<Stats>('/admin/stats')

  useEffect(() => setOpen(false), [location.pathname])

  if (!user || !site) return null
  const s = site.settings
  const today = site.today

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
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? 'is-active' : '')}
            >
              <Icon name={item.icon} size={19} />
              <span>{item.label}</span>
              {item.to === '/admin/orders' && (stats?.orders_new ?? 0) > 0 && <b className="admin-nav__badge">{stats?.orders_new}</b>}
            </NavLink>
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
            <h1>{TITLES[location.pathname] ?? 'Админ-панель'}</h1>
            <span className="admin-topbar__status">
              <span className={`dot ${today.is_closed ? 'dot--muted' : ''}`} />
              {today.is_closed ? 'Павильон закрыт' : `Открыто до ${today.close}`}
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
