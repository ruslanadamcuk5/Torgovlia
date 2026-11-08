import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { platformApi, usePlatformApi } from '../../lib/platformApi'

interface Daily {
  date: string
  visits: number
  visitors: number
  demos: number
  admins: number
  signups: number
  created: number
}

interface AnalyticsData {
  days: number
  generated_at: string
  summary: {
    visits: number
    visitors: number
    demos: number
    demo_sessions: number
    admins: number
    admin_sessions: number
    signup_starts: number
    signup_created: number
    platform_logins: number
    online_30m: number
    visits_24h: number
    demo_24h: number
    signups_24h: number
    visit_to_demo: number
    demo_to_admin: number
    visit_to_signup: number
    signup_to_created: number
  }
  funnel: { code: string; title: string; value: number }[]
  daily: Daily[]
  sources: { source: string; count: number }[]
  pages: { path: string; count: number }[]
  recent: {
    id: number
    kind: string
    title: string
    path: string
    source: string
    detail: string
    created_at: string
  }[]
  tenants: { id: number; name: string; slug: string; created_at: string }[]
}

interface DemoInfo {
  enabled: boolean
  slug: string
  name: string
  storefront_url: string
  admin_url: string
  phone: string
  password: string
  reset_every_hours: number
  reset_at?: string | null
}

const PERIODS = [
  { days: 7, title: '7 дней' },
  { days: 30, title: '30 дней' },
  { days: 90, title: '90 дней' },
]

function shortDate(value: string): string {
  const date = new Date(`${value}T00:00:00`)
  return date.toLocaleDateString('ru-BY', { day: '2-digit', month: '2-digit' })
}

function timeLabel(value: string): string {
  return new Date(value).toLocaleString('ru-BY', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function funnelWidth(value: number, top: number): number {
  if (!top) return 0
  return Math.max(value ? 4 : 0, Math.round((value / top) * 100))
}

export default function PlatformAnalytics() {
  const [days, setDays] = useState(30)
  const { data, loading } = usePlatformApi<AnalyticsData>(`/analytics?days=${days}`)
  const { data: demo, reload: reloadDemo } = usePlatformApi<DemoInfo>('/demo')
  const [resetting, setResetting] = useState(false)
  const [resetMessage, setResetMessage] = useState('')

  const resetDemo = async () => {
    setResetting(true)
    setResetMessage('')
    try {
      await platformApi('/demo/reset', { method: 'POST' })
      setResetMessage('Демо сброшено: данные вернулись к исходному состоянию.')
      reloadDemo()
    } catch (error) {
      setResetMessage(error instanceof Error ? error.message : 'Не удалось сбросить демо')
    } finally {
      setResetting(false)
    }
  }

  const maxDaily = useMemo(
    () =>
      Math.max(
        1,
        ...(data?.daily ?? []).map((row) => Math.max(row.visitors, row.demos, row.signups)),
      ),
    [data],
  )

  const s = data?.summary
  const top = data?.funnel[0]?.value ?? 0

  return (
    <div className="platform-page analytics-page">
      <section className="panel analytics-head">
        <div>
          <h2>Интерес к платформе</h2>
          <p className="muted">
            Сколько людей заходят на сайт продаж, смотрят демо, открывают админку и
            начинают регистрацию. Данные обезличены: только сессия, источник и время.
          </p>
        </div>
        <div className="analytics-period">
          {PERIODS.map((item) => (
            <button
              key={item.days}
              type="button"
              className={days === item.days ? 'is-active' : ''}
              onClick={() => setDays(item.days)}
            >
              {item.title}
            </button>
          ))}
        </div>
      </section>

      {demo?.enabled && (
        <section className="panel analytics-demo">
          <div>
            <h3>Демо-магазин «{demo.name}»</h3>
            <p className="muted">
              Его открывают с сайта продаж. Сброс возвращает витрину и админку к
              исходному состоянию: заказы, чаты, корзины и рассылки создаются заново.
            </p>
            <p className="muted">
              Автосброс: каждые {demo.reset_every_hours} ч
              {demo.reset_at ? ` · последний: ${timeLabel(demo.reset_at)}` : ''}
            </p>
          </div>
          <div className="analytics-demo__actions">
            <a href={demo.storefront_url} target="_blank" rel="noreferrer" className="btn btn--sm btn--ghost">
              Открыть витрину
            </a>
            <a href={demo.admin_url} target="_blank" rel="noreferrer" className="btn btn--sm btn--ghost">
              Открыть админку
            </a>
            <button type="button" className="btn btn--sm btn--outline" disabled={resetting} onClick={resetDemo}>
              {resetting ? 'Сбрасываем…' : 'Сбросить демо'}
            </button>
          </div>
          {resetMessage && <p className="analytics-demo__message">{resetMessage}</p>}
        </section>
      )}

      <section className="platform-stats analytics-kpi">
        <div className="panel">
          <span>Посетителей</span>
          <strong>{s?.visitors ?? '—'}</strong>
          <small className="muted">визитов: {s?.visits ?? 0} · за сутки {s?.visits_24h ?? 0}</small>
        </div>
        <div className="panel">
          <span>Открыли демо</span>
          <strong>{s?.demo_sessions ?? '—'}</strong>
          <small className="muted">{s ? `${s.visit_to_demo}% от посетителей` : ''}</small>
        </div>
        <div className="panel">
          <span>Зашли в админку демо</span>
          <strong>{s?.admin_sessions ?? '—'}</strong>
          <small className="muted">{s ? `${s.demo_to_admin}% от демо` : ''}</small>
        </div>
        <div className="panel">
          <span>Начали регистрацию</span>
          <strong>{s?.signup_starts ?? '—'}</strong>
          <small className="muted">{s ? `${s.visit_to_signup}% от посетителей` : ''}</small>
        </div>
        <div className="panel">
          <span>Создали магазин</span>
          <strong>{s?.signup_created ?? '—'}</strong>
          <small className="muted">{s ? `${s.signup_to_created}% от начавших` : ''}</small>
        </div>
        <div className="panel">
          <span>Сейчас на сайте</span>
          <strong>{s?.online_30m ?? '—'}</strong>
          <small className="muted">уникальных сессий за 30 минут</small>
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Воронка интереса</h2>
            <p className="muted">От первого визита до оплаченного магазина.</p>
          </div>
          <span className="badge badge--muted">за {days} дней</span>
        </div>
        <div className="funnel">
          {(data?.funnel ?? []).map((step, index) => {
            const previous = index > 0 ? data?.funnel[index - 1].value ?? 0 : 0
            const conversion =
              index === 0 || !previous ? null : Math.round((step.value * 100) / previous)
            return (
              <div className="funnel__row" key={step.code}>
                <span className="funnel__label">{step.title}</span>
                <div className="funnel__track">
                  <span style={{ width: `${funnelWidth(step.value, top)}%` }} />
                </div>
                <strong>{step.value}</strong>
                <small>{conversion === null ? 'старт' : `${conversion}%`}</small>
              </div>
            )
          })}
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Динамика по дням</h2>
            <p className="muted">
              <span className="dot dot--teal" /> посетители
              <span className="dot dot--gold" /> демо
              <span className="dot dot--ink" /> регистрации
            </p>
          </div>
          {loading && <span className="muted">Обновляем…</span>}
        </div>
        <div className="chart" role="img" aria-label="Визиты, демо и регистрации по дням">
          {(data?.daily ?? []).map((row) => (
            <div className="chart__day" key={row.date} title={`${row.date}: визиты ${row.visitors}, демо ${row.demos}, регистрации ${row.signups}`}>
              <div className="chart__bars">
                <span className="chart__bar chart__bar--teal" style={{ height: `${(row.visitors / maxDaily) * 100}%` }} />
                <span className="chart__bar chart__bar--gold" style={{ height: `${(row.demos / maxDaily) * 100}%` }} />
                <span className="chart__bar chart__bar--ink" style={{ height: `${(row.signups / maxDaily) * 100}%` }} />
              </div>
              <small>{shortDate(row.date)}</small>
            </div>
          ))}
          {!data?.daily.length && <p className="muted">Пока нет данных за период.</p>}
        </div>
      </section>

      <section className="analytics-columns">
        <div className="panel">
          <div className="panel__head"><h3>Источники переходов</h3></div>
          <div className="analytics-list">
            {(data?.sources ?? []).map((row) => (
              <div className="analytics-list__row" key={row.source}>
                <span>{row.source}</span>
                <strong>{row.count}</strong>
              </div>
            ))}
            {!data?.sources.length && <p className="muted">Источники появятся с первыми визитами.</p>}
          </div>
        </div>
        <div className="panel">
          <div className="panel__head"><h3>Страницы интереса</h3></div>
          <div className="analytics-list">
            {(data?.pages ?? []).map((row) => (
              <div className="analytics-list__row" key={row.path}>
                <span>{row.path}</span>
                <strong>{row.count}</strong>
              </div>
            ))}
            {!data?.pages.length && <p className="muted">Пока нет просмотров.</p>}
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Последние события</h2>
            <p className="muted">Кто и когда интересовался продуктом и покупкой.</p>
          </div>
        </div>
        <div className="platform-table-wrap">
          <table className="platform-table">
            <thead>
              <tr><th>Когда</th><th>Событие</th><th>Источник</th><th>Страница</th><th>Детали</th></tr>
            </thead>
            <tbody>
              {(data?.recent ?? []).map((event) => (
                <tr key={event.id}>
                  <td>{timeLabel(event.created_at)}</td>
                  <td><span className={`event event--${event.kind}`}>{event.title}</span></td>
                  <td>{event.source}</td>
                  <td>{event.path || '—'}</td>
                  <td className="muted">{event.detail || '—'}</td>
                </tr>
              ))}
              {!data?.recent.length && (
                <tr><td colSpan={5} className="muted">События появятся, когда посетители откроют сайт платформы.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {Boolean(data?.tenants.length) && (
        <section className="panel">
          <div className="panel__head"><h3>Новые магазины за период</h3></div>
          <div className="analytics-list">
            {(data?.tenants ?? []).map((tenant) => (
              <div className="analytics-list__row" key={tenant.id}>
                <Link to={`/platform/tenants/${tenant.id}`}>{tenant.name}</Link>
                <span className="muted">/{tenant.slug} · {timeLabel(tenant.created_at)}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
