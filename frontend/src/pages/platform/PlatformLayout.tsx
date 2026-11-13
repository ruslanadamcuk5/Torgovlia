import { Fragment, useEffect, useState } from 'react'
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { getPlatformToken, platformAuthApi, setPlatformToken } from '../../lib/platformApi'
import type { PlatformUser } from '../../lib/types'
import { Icon, type IconName } from '../../components/icons'
import { useScrollReveal } from '../../lib/reveal'

const NAV: { to: string; label: string; icon: IconName; group: string; end?: boolean }[] = [
  { to: '/platform', label: 'Обзор', icon: 'dashboard', group: 'Платформа', end: true },
  { to: '/platform/tenants', label: 'Магазины', icon: 'box', group: 'Платформа' },
  { to: '/platform/analytics', label: 'Интерес и спрос', icon: 'chart', group: 'Платформа' },
  { to: '/platform/catalog', label: 'Сервисы и тарифы', icon: 'grid', group: 'Продукт' },
  { to: '/platform/invoices', label: 'Счета', icon: 'wallet', group: 'Продукт' },
  { to: '/platform/ops', label: 'Запуск и мониторинг', icon: 'refresh', group: 'Эксплуатация' },
  { to: '/platform/incidents', label: 'Инциденты', icon: 'alert', group: 'Эксплуатация' },
  { to: '/platform/audit', label: 'Журнал действий', icon: 'list', group: 'Эксплуатация' },
  { to: '/platform/team', label: 'Команда', icon: 'users', group: 'Доступ' },
  { to: '/platform/settings', label: 'Настройки', icon: 'settings', group: 'Доступ' },
]

const TITLES: Record<string, string> = {
  '/platform/invoices': 'Счета и оплата',
  '/platform/ops': 'Запуск и мониторинг сайтов',
  '/platform/audit': 'Журнал действий платформы',
  '/platform/incidents': 'Инциденты и статус-страница',
  '/platform/settings': 'Глобальные настройки платформы',
  '/platform/analytics': 'Интерес к платформе',
  '/platform/team': 'Команда платформы',
  '/platform/catalog': 'Сервисы и тарифы',
  '/platform/tenants': 'Магазины платформы',
  '/platform': 'Обзор платформы',
}

export default function PlatformLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  useScrollReveal()
  const [user, setUser] = useState<PlatformUser | null>(null)
  const [checking, setChecking] = useState(true)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!getPlatformToken()) {
      setChecking(false)
      return
    }
    platformAuthApi
      .me()
      .then(setUser)
      .catch(() => setPlatformToken(null))
      .finally(() => setChecking(false))
  }, [])

  useEffect(() => {
    const expired = () => navigate('/platform/login', { replace: true })
    window.addEventListener('platform:expired', expired)
    return () => window.removeEventListener('platform:expired', expired)
  }, [navigate])

  useEffect(() => {
    setOpen(false)
  }, [location.pathname])

  if (!getPlatformToken()) return <Navigate to="/platform/login" replace />
  if (checking) return <div className="loader-block">Проверяем доступ…</div>
  if (!user) return <Navigate to="/platform/login" replace />

  const logout = () => {
    setPlatformToken(null)
    navigate('/platform/login', { replace: true })
  }

  const pageTitle = TITLES[location.pathname]
    ?? (location.pathname.startsWith('/platform/tenants/') ? 'Магазин платформы' : 'Панель платформы')

  return (
    <div className="admin-shell platform-shell">
      <aside className={`admin-sidebar ${open ? 'is-open' : ''}`}>
        <Link to="/platform" className="admin-brand">
          <span className="platform-logo platform-logo--sm">T</span>
          <span><strong>Платформа</strong><small>Центральное управление</small></span>
        </Link>

        <div className="admin-place">
          <Icon name="user" size={16} />
          <div>
            <strong>{user.full_name}</strong>
            <span>{user.phone}</span>
          </div>
        </div>

        <nav className="admin-nav">
          {NAV.map((item, index) => (
            <Fragment key={item.to}>
              {(index === 0 || NAV[index - 1].group !== item.group) && (
                <span className="admin-nav__group">{item.group}</span>
              )}
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) => (isActive ? 'is-active' : '')}
              >
                <Icon name={item.icon} size={18} />
                <span>{item.label}</span>
              </NavLink>
            </Fragment>
          ))}
        </nav>

        <div className="admin-sidebar__foot">
          <Link to="/" className="admin-side-link"><Icon name="external" size={16} /> Сайт платформы</Link>
          <Link to="/shop/odezhda/" className="admin-side-link"><Icon name="eye" size={16} /> Демо магазина</Link>
          <div className="admin-user">
            <span className="avatar avatar--sm">{user.full_name.slice(0, 1).toUpperCase()}</span>
            <div><strong>{user.full_name}</strong><span>{user.role}</span></div>
            <button type="button" className="icon-btn" aria-label="Выйти" onClick={logout}>
              <Icon name="logout" size={17} />
            </button>
          </div>
        </div>
      </aside>

      {open && <button type="button" className="admin-overlay" aria-label="Закрыть меню" onClick={() => setOpen(false)} />}

      <div className="admin-main">
        <header className="admin-topbar">
          <button type="button" className="icon-btn admin-burger" onClick={() => setOpen(true)} aria-label="Меню">
            <Icon name="menu" size={22} />
          </button>
          <div className="admin-topbar__title">
            <h1>{pageTitle}</h1>
            <span className="admin-topbar__status">
              <span className="dot" />
              Платформа работает
            </span>
          </div>
          <div className="admin-topbar__actions">
            <Link to="/" className="btn btn--sm btn--ghost"><Icon name="eye" size={16} /> <span>Сайт</span></Link>
            <Link to="/platform/incidents" className="admin-topbar__bell" aria-label="Инциденты">
              <Icon name="bell" size={19} />
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
