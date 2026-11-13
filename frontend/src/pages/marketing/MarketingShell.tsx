import { useEffect, useState, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Icon } from '../../components/icons'

const NAV_ITEMS = [
  { id: 'possibilities', label: 'Возможности' },
  { id: 'demos', label: 'Демо' },
  { id: 'templates', label: 'Шаблоны' },
  { id: 'pricing', label: 'Тарифы' },
  { id: 'faq', label: 'Вопросы' },
]

export default function MarketingShell({ children }: { children: ReactNode }) {
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const onHome = location.pathname === '/'

  useEffect(() => {
    setOpen(false)
  }, [location.pathname])

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 14)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  const anchor = (id: string) => (onHome ? `#${id}` : `/#${id}`)

  return (
    <div className="mkt lp">
      <div className="lp-topbar">
        <span className="lp-topbar__dot" />
        <span>Демо магазина и салона открыто — вход в админку без логина и пароля</span>
        <a href={anchor('demos')}>Открыть демо <Icon name="arrow-right" size={12} /></a>
      </div>

      <header className={`lp-nav ${scrolled ? 'is-scrolled' : ''}`}>
        <div className="lp-nav__inner">
          <Link to="/" className="lp-brand" aria-label="Торговля — на главную">
            <span className="lp-brand__mark">
              <span>Т</span>
            </span>
            <span className="lp-brand__text">
              <strong>Торговля</strong>
              <small>товары и услуги · одна платформа</small>
            </span>
          </Link>

          <nav className="lp-nav__links" aria-label="Разделы страницы">
            {NAV_ITEMS.map((item) => (
              <a key={item.id} href={anchor(item.id)}>{item.label}</a>
            ))}
          </nav>

          <div className="lp-nav__actions">
            <Link to="/platform/login" className="lp-btn lp-btn--ghost lp-btn--sm">
              <Icon name="lock" size={13} /> Панель
            </Link>
            <Link to="/new" className="lp-btn lp-btn--primary lp-btn--sm">
              Создать сайт <Icon name="arrow-right" size={14} />
            </Link>
          </div>

          <button
            type="button"
            className={`lp-nav__burger ${open ? 'is-open' : ''}`}
            aria-label={open ? 'Закрыть меню' : 'Открыть меню'}
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            <span /><span /><span />
          </button>
        </div>

        <div className={`lp-menu ${open ? 'is-open' : ''}`}>
          <nav aria-label="Мобильное меню">
            {NAV_ITEMS.map((item) => (
              <a key={item.id} href={anchor(item.id)} onClick={() => setOpen(false)}>
                {item.label} <Icon name="arrow-right" size={14} />
              </a>
            ))}
          </nav>
          <div className="lp-menu__actions">
            <Link to="/platform/login" className="lp-btn lp-btn--ghost lp-btn--block">
              <Icon name="lock" size={14} /> Панель платформы
            </Link>
            <Link to="/new" className="lp-btn lp-btn--primary lp-btn--block">
              Создать сайт <Icon name="arrow-right" size={14} />
            </Link>
          </div>
          <span className="lp-menu__note">
            <Icon name="sparkles" size={14} /> Демо без логина и пароля
          </span>
        </div>
      </header>

      <main className="lp-main">{children}</main>

      <footer className="lp-foot">
        <div className="lp-foot__glow" aria-hidden="true" />
        <div className="lp-foot__top">
          <div className="lp-foot__brand">
            <Link to="/" className="lp-brand">
              <span className="lp-brand__mark"><span>Т</span></span>
              <span className="lp-brand__text">
                <strong>Торговля</strong>
                <small>товары и услуги · одна платформа</small>
              </span>
            </Link>
            <p>
              Витрина, заказы, склад и клиенты рядом с услугами, специалистами
              и онлайн-записью. Запуск на поддомене, свой домен, счёт и поддержка.
            </p>
            <div className="lp-foot__demos">
              <a href="/shop/odezhda/">Демо магазина <Icon name="external" size={12} /></a>
              <a href="/shop/salon/">Демо салона <Icon name="external" size={12} /></a>
            </div>
          </div>

          <div className="lp-foot__col">
            <strong>Продукт</strong>
            <a href={anchor('possibilities')}>Возможности</a>
            <a href={anchor('demos')}>Живое демо</a>
            <a href={anchor('templates')}>Шаблоны и категории</a>
            <a href={anchor('pricing')}>Тарифы</a>
          </div>

          <div className="lp-foot__col">
            <strong>Платформа</strong>
            <Link to="/platform/login">Панель платформы</Link>
            <Link to="/status">Статус платформы</Link>
            <Link to="/new">Создать сайт</Link>
            <a href="mailto:hello@torgovlia.by">hello@torgovlia.by</a>
          </div>

          <div className="lp-foot__col">
            <strong>Документы</strong>
            <a href={anchor('faq')}>Вопросы и ответы</a>
            <a href={anchor('how')}>Как это работает</a>
            <span>Оферта и политика — при запуске</span>
            <span>Минск, Беларусь</span>
          </div>
        </div>

        <div className="lp-foot__bottom">
          <span>© {new Date().getFullYear()} Торговля. Все права защищены.</span>
          <span className="lp-foot__live">
            <i /> Сервисы работают · мониторинг 24/7
          </span>
          <span>Сделано для небольших магазинов и салонов</span>
        </div>
      </footer>
    </div>
  )
}
