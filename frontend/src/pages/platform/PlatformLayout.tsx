import { useEffect, useState } from 'react'
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { getPlatformToken, platformAuthApi, setPlatformToken } from '../../lib/platformApi'
import type { PlatformUser } from '../../lib/types'

const NAV = [
  { to: '/platform', label: 'Обзор', end: true },
  { to: '/platform/tenants', label: 'Магазины' },
  { to: '/platform/catalog', label: 'Сервисы и тарифы' },
  { to: '/platform/invoices', label: 'Счета' },
  { to: '/platform/ops', label: 'Запуск и мониторинг' },
  { to: '/platform/incidents', label: 'Инциденты' },
  { to: '/platform/audit', label: 'Журнал действий' },
]

export default function PlatformLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const [user, setUser] = useState<PlatformUser | null>(null)
  const [checking, setChecking] = useState(true)

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

  if (!getPlatformToken()) return <Navigate to="/platform/login" replace />
  if (checking) return <div className="loader-block">Проверяем доступ…</div>
  if (!user) return <Navigate to="/platform/login" replace />

  const logout = () => {
    setPlatformToken(null)
    navigate('/platform/login', { replace: true })
  }

  return (
    <div className="admin-shell platform-shell">
      <aside className="admin-sidebar">
        <Link to="/platform" className="admin-brand">
          <span className="platform-logo platform-logo--sm">T</span>
          <span><strong>Платформа</strong><small>Центральное управление</small></span>
        </Link>

        <div className="admin-place">
          <div>
            <strong>{user.full_name}</strong>
            <span>{user.phone}</span>
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
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="admin-sidebar__foot">
          <div className="admin-user">
            <span className="avatar avatar--sm">{user.full_name.slice(0, 1).toUpperCase()}</span>
            <div><strong>{user.full_name}</strong><span>{user.role}</span></div>
            <button type="button" className="icon-btn" aria-label="Выйти" onClick={logout}>Выйти</button>
          </div>
        </div>
      </aside>

      <div className="admin-main">
        <header className="admin-topbar">
          <div className="admin-topbar__title">
            <h1>{location.pathname === '/platform'
              ? 'Обзор платформы'
              : location.pathname.startsWith('/platform/tenants')
                ? 'Магазины платформы'
                : location.pathname === '/platform/invoices'
                  ? 'Счета и оплата'
                  : location.pathname === '/platform/ops'
                    ? 'Запуск и мониторинг сайтов'
                    : location.pathname === '/platform/audit'
                      ? 'Журнал действий платформы'
                      : location.pathname === '/platform/incidents'
                        ? 'Инциденты и статус-страница'
                        : 'Сервисы и тарифы'}</h1>
          </div>
        </header>
        <div className="admin-content">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
