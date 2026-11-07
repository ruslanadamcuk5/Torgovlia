import { Link } from 'react-router-dom'
import { usePlatformApi } from '../../lib/platformApi'
import type { DashboardMetrics, Tenant } from '../../lib/types'

const STATUS_LABEL: Record<string, string> = {
  draft: 'Черновик',
  onboarding: 'Настройка',
  active: 'Активен',
  grace: 'Отсрочка',
  suspended: 'Приостановлен',
  archived: 'Архив',
}

export default function PlatformOverview() {
  const { data: stats } = usePlatformApi<DashboardMetrics>('/dashboard')
  const { data: tenants } = usePlatformApi<{ items: Tenant[]; total: number }>('/tenants?limit=6')

  return (
    <div className="platform-page">
      <section className="platform-stats">
        <div className="panel"><span>MRR</span><strong>{stats ? `${stats.mrr.toFixed(2)} ` : '—'}<small>BYN</small></strong></div>
        <div className="panel"><span>Активных магазинов</span><strong>{stats?.tenants_active ?? '—'}</strong></div>
        <div className="panel"><span>На настройке</span><strong>{stats?.tenants_onboarding ?? '—'}</strong></div>
        <div className="panel"><span>Требуют внимания</span><strong>{stats?.attention_total ?? '—'}</strong></div>
      </section>

      <section className="platform-stats platform-stats--secondary">
        <div className="panel"><span>ARR</span><strong>{stats ? `${stats.arr.toFixed(2)} ` : '—'}<small>BYN</small></strong></div>
        <div className="panel"><span>Оплачено за 30 дней</span><strong>{stats ? `${stats.paid_30d.toFixed(2)} ` : '—'}<small>BYN</small></strong></div>
        <div className="panel"><span>К оплате</span><strong>{stats?.open_invoices_count ?? '—'}</strong><small className="muted">{stats ? `${stats.open_invoices_total.toFixed(2)} BYN` : ''}</small></div>
        <div className="panel"><span>Новых за 30 дней</span><strong>{stats?.new_30d ?? '—'}</strong></div>
        <div className="panel"><span>В очереди запуска</span><strong>{stats?.queue_total ?? '—'}</strong></div>
        <div className="panel"><span>Подписок</span><strong>{stats?.paying_tenants ?? '—'}</strong><small className="muted">план + доп. услуги: {stats ? `${stats.mrr_plans.toFixed(2)} / ${stats.mrr_addons.toFixed(2)}` : '—'}</small></div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Последние магазины</h2>
            <p className="muted">Быстрый переход в карточку и управление сервисами.</p>
          </div>
          <Link to="/platform/tenants" className="btn btn--sm btn--outline">Все магазины</Link>
        </div>

        <div className="platform-table-wrap">
          <table className="platform-table">
            <thead>
              <tr><th>Магазин</th><th>Домен</th><th>Тариф</th><th>Статус</th></tr>
            </thead>
            <tbody>
              {(tenants?.items ?? []).map((tenant) => (
                <tr key={tenant.id}>
                  <td>
                    <Link to={`/platform/tenants/${tenant.id}`}><strong>{tenant.name}</strong></Link>
                    <span className="muted"> /{tenant.slug}</span>
                  </td>
                  <td>{tenant.domains.find((item) => item.is_primary)?.host ?? '—'}</td>
                  <td>{tenant.plan_code}</td>
                  <td><span className={`badge ${tenant.status === 'active' ? 'badge--fresh' : 'badge--muted'}`}>{STATUS_LABEL[tenant.status] ?? tenant.status}</span></td>
                </tr>
              ))}
              {!tenants?.items.length && (
                <tr><td colSpan={4} className="muted">Магазинов пока нет.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="platform-quick">
        <Link to="/platform/tenants" className="panel platform-quick__item">
          <strong>Добавить магазин</strong>
          <span>Создать арендатора, домен и владельца за один шаг.</span>
        </Link>
        <Link to="/platform/catalog" className="panel platform-quick__item">
          <strong>Каталог сервисов</strong>
          <span>Тарифы, состав услуг и точки подключения.</span>
        </Link>
        <Link to="/platform/ops" className="panel platform-quick__item">
          <strong>Запуск и мониторинг</strong>
          <span>Очередь провижининга, хостинг, SSL и состояние сайтов.</span>
        </Link>
      </section>
    </div>
  )
}
