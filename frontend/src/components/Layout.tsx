import { useEffect } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useSite } from '../store/SettingsContext'
import { assetUrl } from '../lib/api'
import { useAuth } from '../store/AuthContext'
import { useCart } from '../store/CartContext'
import { Icon } from './icons'
import { SocialLinks } from './SocialLinks'
import { Loader } from './ui'
import { useState } from 'react'

const NAV = [
  { to: '/catalog', label: 'Каталог' },
  { to: '/articles', label: 'О рыбе' },
  { to: '/pickup', label: 'Как забрать' },
  { to: '/app', label: 'Приложение' },
  { to: '/contacts', label: 'Контакты' },
]

function scrollTop() {
  window.scrollTo(0, 0)
}

export function ScrollToTop() {
  const location = useLocation()
  useEffect(() => {
    scrollTop()
    // Браузер иногда восстанавливает позицию после первого рендера.
    // Повторяем сброс в следующем кадре, чтобы страница всегда открывалась сверху.
    let frame = requestAnimationFrame(() => {
      scrollTop()
      frame = requestAnimationFrame(scrollTop)
    })
    const timer = window.setTimeout(scrollTop, 80)
    return () => {
      cancelAnimationFrame(frame)
      clearTimeout(timer)
    }
  }, [location.pathname, location.search])
  return null
}

export function Header() {
  const { site } = useSite()
  const { user, isStaff, isAdmin } = useAuth()
  const { count } = useCart()
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    setOpen(false)
  }, [location.pathname])

  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : ''
    return () => {
      document.body.style.overflow = ''
    }
  }, [open])

  if (!site) return null
  const s = site.settings
  const today = site.today

  return (
    <header className="header">
      <div className="topbar">
        <div className="container topbar__inner">
          <span className="topbar__location">
            <Icon name="pin" size={15} />
            <strong>{s.city}</strong>
            <span className="topbar__sep">·</span>
            {s.market_name}
            <span className="topbar__sep">·</span>
            {s.pavilion}
          </span>
          <span className="topbar__right">
            <span className={`topbar__hours ${today.is_closed ? 'is-closed' : ''}`}>
              <span className="dot" />
              {today.is_closed ? 'Сегодня закрыто' : `Сегодня ${today.open}–${today.close}`}
            </span>
            <a href={`tel:${s.phone.replace(/[^\d+]/g, '')}`} className="topbar__phone">
              <Icon name="phone" size={15} /> {s.phone}
            </a>
          </span>
        </div>
      </div>

      <div className="header__main">
        <div className="container header__inner">
          <Link to="/" className="brand" aria-label={s.brand_name}>
            <img src={assetUrl(s.logo_url)} alt="" className="brand__logo" width={48} height={48} />
            <span className="brand__text">
              <strong>{s.brand_name}</strong>
              <span>{s.tagline}</span>
            </span>
          </Link>

          <nav className="nav" aria-label="Основная навигация">
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} className={({ isActive }) => (isActive ? 'is-active' : '')}>
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="header__actions">
            {isAdmin && <Link to="/admin" className="header__staff"><Icon name="dashboard" size={18} /><span>Админка</span></Link>}
            {isStaff && <Link to="/seller" className="header__staff"><Icon name="box" size={18} /><span>Рабочий режим</span></Link>}
            <Link to="/cart" className="header__icon" aria-label={`Корзина, позиций: ${count}`}>
              <Icon name="cart" size={22} />
              {count > 0 && <span className="header__badge">{count}</span>}
            </Link>
            <Link to={user ? '/account' : '/login'} className="header__account">
              <Icon name="user" size={20} />
              <span>{user ? user.full_name.split(' ')[0] : 'Войти'}</span>
            </Link>
            <button type="button" className="burger" aria-label="Меню" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
              <Icon name={open ? 'close' : 'menu'} size={24} />
            </button>
          </div>
        </div>
      </div>

      {s.announcement_active && s.announcement && (
        <div className="announce">
          <div className="container announce__inner">
            <Icon name="sparkles" size={16} />
            <span>{s.announcement}</span>
            <Link to="/catalog">Смотреть каталог <Icon name="arrow-right" size={14} /></Link>
          </div>
        </div>
      )}

      {open && (
        <div className="mobile-menu">
          <div className="mobile-menu__head">
            <span className="mobile-menu__title">Меню</span>
            <button type="button" className="icon-btn" onClick={() => setOpen(false)} aria-label="Закрыть меню">
              <Icon name="close" size={22} />
            </button>
          </div>
          <nav className="mobile-menu__nav">
            {NAV.map((item) => (
              <Link key={item.to} to={item.to} onClick={() => setOpen(false)}>
                {item.label}
                <Icon name="chevron-right" size={18} />
              </Link>
            ))}
            <Link to={user ? '/account' : '/login'} onClick={() => setOpen(false)}>
              {user ? 'Личный кабинет' : 'Войти в аккаунт'}
              <Icon name="chevron-right" size={18} />
            </Link>
            <Link to="/cart" onClick={() => setOpen(false)}>
              Корзина {count > 0 ? `(${count})` : ''}
              <Icon name="chevron-right" size={18} />
            </Link>
            {isAdmin && (
              <Link to="/admin" onClick={() => setOpen(false)}>
                Админ-панель
                <Icon name="chevron-right" size={18} />
              </Link>
            )}
            {isStaff && (
              <Link to="/seller" onClick={() => setOpen(false)}>
                Рабочий режим
                <Icon name="chevron-right" size={18} />
              </Link>
            )}
          </nav>
          <div className="mobile-menu__contacts">
            <a href={`tel:${s.phone.replace(/[^\d+]/g, '')}`} className="btn btn--primary btn--block">
              <Icon name="phone" size={18} /> {s.phone}
            </a>
            <SocialLinks socials={s.socials} variant="footer" />
          </div>
        </div>
      )}
    </header>
  )
}

export function Footer() {
  const { site } = useSite()
  if (!site) return null
  const s = site.settings
  const year = new Date().getFullYear()

  return (
    <footer className="footer">
      <div className="container">
        <div className="footer__cta">
          <div>
            <span className="eyebrow eyebrow--light">Самовывоз · без предоплаты</span>
            <h2>Забронируйте рыбу — соберём к вашему приходу</h2>
            <p>{s.city}, {s.market_name}, {s.pavilion}. Оплата наличными или картой при получении.</p>
          </div>
          <div className="footer__cta-actions">
            <Link to="/catalog" className="btn btn--gold btn--lg">Перейти в каталог <Icon name="arrow-right" size={18} /></Link>
            <a href={`tel:${s.phone.replace(/[^\d+]/g, '')}`} className="btn btn--ghost-light btn--lg">{s.phone}</a>
          </div>
        </div>

        <div className="footer__grid">
          <div className="footer__brand">
            <Link to="/" className="brand brand--footer">
              <img src={assetUrl(s.logo_url)} alt="" width={52} height={52} className="brand__logo" />
              <span className="brand__text">
                <strong>{s.brand_name}</strong>
                <span>{s.tagline}</span>
              </span>
            </Link>
            <p>{s.about_text.split('\n')[0]}</p>
            <SocialLinks socials={s.socials} variant="footer" />
          </div>

          <div className="footer__col">
            <h3>Покупателям</h3>
            <Link to="/catalog">Каталог</Link>
            <Link to="/articles">Полезные статьи</Link>
            <Link to="/pickup">Доставка и самовывоз</Link>
            <Link to="/app">Приложение для Android</Link>
            <Link to="/account">Мои брони</Link>
            <Link to="/contacts">Контакты</Link>
          </div>

          <div className="footer__col">
            <h3>Павильон</h3>
            <p className="footer__address"><Icon name="pin" size={16} /> {s.address}</p>
            <a href={`tel:${s.phone.replace(/[^\d+]/g, '')}`}><Icon name="phone" size={16} /> {s.phone}</a>
            {s.phone_secondary && <a href={`tel:${s.phone_secondary.replace(/[^\d+]/g, '')}`}>{s.phone_secondary}</a>}
            <a href={`mailto:${s.email}`}><Icon name="mail" size={16} /> {s.email}</a>
            <div className="footer__hours">
              <Icon name="clock" size={16} />
              <div>
                {s.working_hours.map((day) => (
                  <span key={day.weekday} className={day.closed ? 'is-closed' : ''}>
                    {day.label.slice(0, 2)} — {day.closed ? 'выходной' : `${day.open}–${day.close}`}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="footer__col footer__col--documents">
            <h3>Документы</h3>
            <Link to="/legal/privacy">Политика обработки персональных данных</Link>
            <Link to="/legal/offer">Правила бронирования</Link>
            <Link to="/legal/pickup">Условия самовывоза</Link>
            <Link to="/legal/returns">Возврат и качество</Link>
            <Link to="/admin" className="footer__admin-link">Панель администратора</Link>
          </div>
        </div>

        <div className="footer__requisites">
          <div>
            <strong>{s.legal_name}</strong>
            <span>УНП {s.unp}</span>
            <span>{s.legal_address || s.address}</span>
            <span>Свидетельство о государственной регистрации ИП — по запросу.</span>
          </div>
          <div className="footer__legal">
            <span>© {year} {s.brand_name}. Все права защищены.</span>
            <span>Информация на сайте носит справочный характер и не является публичной офертой.</span>
            <span>Доставка не осуществляется. Оплата при получении в павильоне.</span>
          </div>
        </div>
      </div>
    </footer>
  )
}

export function CookieBanner() {
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    setVisible(!localStorage.getItem('rl_cookie_ok'))
  }, [])
  if (!visible) return null
  return (
    <div className="cookie">
      <p>
        Мы используем cookie для работы корзины и авторизации. Продолжая пользоваться сайтом, вы соглашаетесь с{' '}
        <Link to="/legal/privacy">политикой обработки персональных данных</Link>.
      </p>
      <button
        type="button"
        className="btn btn--sm btn--primary"
        onClick={() => {
          localStorage.setItem('rl_cookie_ok', '1')
          setVisible(false)
        }}
      >
        Принять
      </button>
    </div>
  )
}

export function PublicLayout() {
  const { site, loading, error, refresh } = useSite()

  if (loading && !site) {
    return (
      <div className="page-loader">
        <img src="/assets/logo.svg" alt="" width={64} height={64} />
        <Loader label="Открываем рыбную лавку…" />
      </div>
    )
  }

  if (error && !site) {
    return (
      <div className="page-loader">
        <Icon name="alert" size={40} />
        <h1>Сайт временно недоступен</h1>
        <p>{error}</p>
        <button type="button" className="btn btn--primary" onClick={() => void refresh()}>
          <Icon name="refresh" size={18} /> Повторить
        </button>
      </div>
    )
  }

  return (
    <div className="app">
      <Header />
      <main>
        <Outlet />
      </main>
      <Footer />
      <CookieBanner />
      <MobileBar />
      <button type="button" className="to-top" onClick={scrollTop} aria-label="Наверх">
        <Icon name="arrow-left" size={18} />
      </button>
    </div>
  )
}

function MobileBar() {
  const { count } = useCart()
  const { user } = useAuth()
  const location = useLocation()
  if (location.pathname.startsWith('/admin') || location.pathname.startsWith('/seller')) return null
  return (
    <nav className="mobile-bar" aria-label="Быстрая навигация">
      <NavLink to="/" end><Icon name="fish" size={21} /><span>Главная</span></NavLink>
      <NavLink to="/catalog"><Icon name="search" size={21} /><span>Каталог</span></NavLink>
      <NavLink to="/cart" className="mobile-bar__cart">
        <span className="mobile-bar__cart-icon">
          <Icon name="cart" size={22} />
          {count > 0 && <b>{count}</b>}
        </span>
        <span>Корзина</span>
      </NavLink>
      <NavLink to={user ? '/account' : '/login'}><Icon name="user" size={21} /><span>{user ? 'Кабинет' : 'Войти'}</span></NavLink>
    </nav>
  )
}
