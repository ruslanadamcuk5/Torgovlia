import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export default function MarketingShell({ children }: { children: ReactNode }) {
  return (
    <div className="mkt">
      <header className="mkt-header">
        <Link to="/start" className="mkt-brand">
          <span className="mkt-logo">Т</span>
          <span>
            <strong>Торговля</strong>
            <small>платформа для торговых мест</small>
          </span>
        </Link>
        <nav className="mkt-nav">
          <a href="#features">Возможности</a>
          <a href="#templates">Шаблоны</a>
          <a href="#tariffs">Тарифы</a>
          <a href="#how">Как работает</a>
        </nav>
        <div className="mkt-actions">
          <Link to="/platform/login" className="btn btn--ghost btn--sm">Войти</Link>
          <Link to="/start/new" className="btn btn--primary btn--sm">Создать магазин</Link>
        </div>
      </header>

      <main className="mkt-main">{children}</main>

      <footer className="mkt-footer">
        <div>
          <Link to="/start" className="mkt-brand mkt-brand--footer">
            <span className="mkt-logo">Т</span>
            <span><strong>Торговля</strong><small>магазин для каждого торгового места</small></span>
          </Link>
          <p>Платформа для владельцев павильонов, лотков и небольших магазинов. Запуск на поддомене, свой домен, оплата и поддержка.</p>
        </div>
        <div>
          <strong>Продукт</strong>
          <a href="#features">Возможности</a>
          <a href="#templates">Шаблоны</a>
          <a href="#tariffs">Тарифы</a>
          <Link to="/start/new">Создать магазин</Link>
        </div>
        <div>
          <strong>Платформа</strong>
          <Link to="/platform/login">Панель платформы</Link>
          <Link to="/status">Статус платформы</Link>
          <a href="mailto:hello@torgovlia.by">hello@torgovlia.by</a>
          <span>Минск, Беларусь</span>
        </div>
        <div>
          <strong>Документы</strong>
          <a href="#faq">Вопросы и ответы</a>
          <span>Оферта и политика — при запуске</span>
          <span>© {new Date().getFullYear()} Торговля</span>
        </div>
      </footer>
    </div>
  )
}
