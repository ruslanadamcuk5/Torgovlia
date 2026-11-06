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

export default function PlatformCatalog() {
  const { data, loading } = usePlatformApi<PlatformCatalog>('/catalog')
  const [group, setGroup] = useState('all')

  const groups = useMemo(() => {
    const seen: string[] = []
    for (const item of data?.services ?? []) if (!seen.includes(item.group)) seen.push(item.group)
    return seen
  }, [data])

  const services = (data?.services ?? []).filter((item) => group === 'all' || item.group === group)

  if (loading) return <div className="loader-block">Загружаем каталог…</div>

  return (
    <div className="platform-page">
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

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Сервисы платформы</h2>
            <p className="muted">Что входит в тарифы и что подключается отдельно.</p>
          </div>
          <span className="badge badge--muted">{data?.services.length ?? 0} сервисов</span>
        </div>

        <div className="services-tabs">
          <button type="button" className={group === 'all' ? 'is-active' : ''} onClick={() => setGroup('all')}>Все</button>
          {groups.map((name) => (
            <button key={name} type="button" className={group === name ? 'is-active' : ''} onClick={() => setGroup(name)}>{name}</button>
          ))}
        </div>

        <div className="platform-table-wrap">
          <table className="platform-table platform-table--services">
            <thead>
              <tr>
                <th>Сервис</th><th>Группа</th><th>Уровень</th><th>Цена</th>
                <th>Старт</th><th>Бизнес</th><th>Про</th>
              </tr>
            </thead>
            <tbody>
              {services.map((item) => (
                <tr key={item.code}>
                  <td><strong>{item.title}</strong><br /><span className="muted">{item.code}</span></td>
                  <td>{item.group}</td>
                  <td>{TIER_LABEL[item.tier] ?? item.tier}</td>
                  <td>{item.price_month ? `${item.price_month.toFixed(2)} BYN` : '—'}</td>
                  {['start', 'business', 'pro'].map((plan) => (
                    <td key={plan}>{item.included[plan] ? '✓' : '—'}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
