import { useMemo, useState } from 'react'
import { usePlatformApi } from '../../lib/platformApi'
import type { PlatformCatalog } from '../../lib/types'

const TIER_LABEL: Record<string, string> = {
  free: 'Базовый',
  start: 'Старт',
  business: 'Бизнес',
  pro: 'Про',
  addon: 'Add-on',
  platform: 'Платформа',
}

const STATUS_LABEL: Record<string, string> = {
  ready: 'Готово',
  partial: 'Частично',
  planned: 'В разработке',
}

const STATUS_HINT: Record<string, string> = {
  ready: 'Работает на демо и у клиентов',
  partial: 'Работает, но нужны условия или ручной шаг',
  planned: 'Заявлено в тарифах, функционал ещё не собран',
}

const PLAN_LABEL: Record<string, string> = {
  start: 'Старт',
  business: 'Бизнес',
  pro: 'Про',
}

export default function PlatformCatalog() {
  const { data, loading } = usePlatformApi<PlatformCatalog>('/catalog')
  const [group, setGroup] = useState('all')
  const [status, setStatus] = useState('all')
  const [query, setQuery] = useState('')

  const groups = useMemo(() => {
    const seen: string[] = []
    for (const item of data?.services ?? []) if (!seen.includes(item.group)) seen.push(item.group)
    return seen
  }, [data])

  const services = (data?.services ?? []).filter((item) => {
    if (group !== 'all' && item.group !== group) return false
    if (status !== 'all' && item.status !== status) return false
    if (query.trim()) {
      const haystack = `${item.title} ${item.code} ${item.description}`.toLowerCase()
      if (!haystack.includes(query.trim().toLowerCase())) return false
    }
    return true
  })

  const counts = useMemo(() => {
    const items = data?.services ?? []
    return {
      total: items.length,
      ready: items.filter((item) => item.status === 'ready').length,
      partial: items.filter((item) => item.status === 'partial').length,
      planned: items.filter((item) => item.status === 'planned').length,
    }
  }, [data])

  if (loading) return <div className="loader-block">Загружаем каталог…</div>

  return (
    <div className="platform-page catalog-registry">
      <section className="platform-plans">
        {(data?.plans ?? []).map((plan) => (
          <article key={plan.code} className="panel platform-plan">
            <h3>{plan.title}</h3>
            <strong>{plan.price_month.toFixed(2)} BYN <small>/ мес</small></strong>
            <p>{plan.description}</p>
            <ul>
              <li>Товаров: {plan.quotas.products ? plan.quotas.products : 'без лимита'}</li>
              <li>Хранилище: {plan.quotas.storage_gb} ГБ</li>
              <li>SMS: {plan.quotas.sms_month} / мес</li>
              <li>Сотрудников: {plan.quotas.users}</li>
            </ul>
          </article>
        ))}
      </section>

      <section className="panel registry-summary">
        <div>
          <span className="muted">Всего сервисов</span>
          <strong>{counts.total}</strong>
        </div>
        <div>
          <span className="muted">Готовы к продаже</span>
          <strong>{counts.ready}</strong>
        </div>
        <div>
          <span className="muted">Частично</span>
          <strong>{counts.partial}</strong>
        </div>
        <div>
          <span className="muted">В разработке</span>
          <strong>{counts.planned}</strong>
        </div>
        <div className="registry-summary__legend">
          {(['ready', 'partial', 'planned'] as const).map((code) => (
            <span key={code}>
              <i className={`registry-dot registry-dot--${code}`} /> {STATUS_LABEL[code]} — {STATUS_HINT[code]}
            </span>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Реестр сервисов</h2>
            <p className="muted">
              Описание, тариф, зависимости и честный статус готовности каждого сервиса.
            </p>
          </div>
        </div>

        <div className="registry-toolbar">
          <div className="services-tabs">
            <button type="button" className={group === 'all' ? 'is-active' : ''} onClick={() => setGroup('all')}>
              Все
            </button>
            {groups.map((name) => (
              <button key={name} type="button" className={group === name ? 'is-active' : ''} onClick={() => setGroup(name)}>
                {name}
              </button>
            ))}
          </div>
          <div className="registry-filters">
            <div className="registry-search">
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Найти сервис"
              />
            </div>
            <div className="registry-status">
              {(['all', 'ready', 'partial', 'planned'] as const).map((code) => (
                <button
                  key={code}
                  type="button"
                  className={status === code ? 'is-active' : ''}
                  onClick={() => setStatus(code)}
                >
                  {code === 'all' ? 'Любой статус' : STATUS_LABEL[code]}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="registry-grid">
          {services.map((item) => (
            <article className={`registry-card registry-card--${item.status}`} key={item.code}>
              <header>
                <div>
                  <h3>{item.title}</h3>
                  <span className="registry-card__group">{item.group} · {TIER_LABEL[item.tier] ?? item.tier}</span>
                </div>
                <span className={`registry-badge registry-badge--${item.status}`}>
                  {STATUS_LABEL[item.status]}
                </span>
              </header>

              <p>{item.description}</p>

              {item.status_note && <p className="registry-card__note">{item.status_note}</p>}

              <div className="registry-card__meta">
                <span>{item.price_month ? `${item.price_month.toFixed(2)} BYN / мес` : 'включено в тариф'}</span>
                <span>
                  {Object.entries(item.included)
                    .filter(([, value]) => value)
                    .map(([code]) => PLAN_LABEL[code])
                    .join(' · ') || 'только платно'}
                </span>
              </div>

              {item.dependencies.length > 0 && (
                <p className="registry-card__deps">
                  Нужны сервисы: {item.dependencies.join(', ')}
                </p>
              )}

              <footer>
                <code>{item.code}</code>
                {item.setup_route ? (
                  <span className="muted">Настройка: {item.setup_route}</span>
                ) : (
                  <span className="muted">{item.tier === 'platform' ? 'Управляется платформой' : 'Без отдельного экрана'}</span>
                )}
              </footer>
            </article>
          ))}
          {!services.length && <p className="muted">Ничего не найдено.</p>}
        </div>
      </section>
    </div>
  )
}
