import { Link, useParams } from 'react-router-dom'
import { usePlatformApi } from '../../lib/platformApi'
import type { PlatformServiceDetail, PlatformServiceLink } from '../../lib/types'

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
  ready: 'Сервис работает на демо и у клиентов — его можно продавать.',
  partial: 'Работает, но нужны условия, договор или ручной шаг.',
  planned: 'Заявлено в тарифах, функционал ещё не собран.',
}

const PLAN_LABEL: Record<string, string> = {
  start: 'Старт',
  business: 'Бизнес',
  pro: 'Про',
}

const TENANT_STATUS: Record<string, string> = {
  enabled: 'Включён',
  trial: 'Пробный',
  disabled: 'Выключен',
  pending_payment: 'Ждёт оплаты',
  suspended: 'Приостановлен',
}

const TENANT_STATUS_TONE: Record<string, string> = {
  enabled: 'badge--fresh',
  trial: 'badge--gold',
  pending_payment: 'badge--gold',
  suspended: 'badge--danger',
  disabled: 'badge--muted',
}

export default function PlatformServiceDetail() {
  const { code = '' } = useParams()
  const { data, loading, error } = usePlatformApi<PlatformServiceDetail>(code ? `/catalog/${code}` : null)

  if (loading) return <div className="platform-page"><div className="loader-block">Загружаем сервис…</div></div>
  if (error || !data) {
    return (
      <div className="platform-page">
        <Link to="/platform/catalog" className="detail-back">← Реестр сервисов</Link>
        <section className="panel">
          <h2>Сервис не найден</h2>
          <p className="muted">{error ?? 'Проверьте код сервиса в реестре.'}</p>
        </section>
      </div>
    )
  }

  const plans = Object.entries(data.included)
    .filter(([, value]) => value)
    .map(([plan]) => PLAN_LABEL[plan] ?? plan)
  const activeTenants = data.usage.tenants.filter((tenant) => tenant.enabled)

  return (
    <div className="platform-page service-detail">
      <Link to="/platform/catalog" className="detail-back">← Реестр сервисов</Link>

      <section className={`panel service-detail__hero registry-card--${data.status}`}>
        <div className="service-detail__intro">
          <span className="service-card__group">{data.group} · код {data.code}</span>
          <h1>{data.title}</h1>
          <div className="service-detail__badges">
            <span className={`registry-badge registry-badge--${data.status}`}>{STATUS_LABEL[data.status]}</span>
            <span className="service-tier">{TIER_LABEL[data.tier] ?? data.tier}</span>
            {data.price_month > 0 && (
              <span className="service-tier service-tier--addon">{data.price_month.toFixed(2)} BYN / мес</span>
            )}
          </div>
          <p className="service-detail__about">{data.about}</p>
          {data.audience && <p className="service-detail__audience">{data.audience}</p>}
          <p className={`service-detail__readiness service-detail__readiness--${data.status}`}>
            <strong>{data.status_title}</strong>
            {data.status_note ? ` — ${data.status_note}` : ` — ${STATUS_HINT[data.status]}`}
          </p>
        </div>

        <dl className="service-detail__facts">
          <div>
            <dt>Тариф</dt>
            <dd>{TIER_LABEL[data.tier] ?? data.tier}</dd>
          </div>
          <div>
            <dt>Цена</dt>
            <dd>{data.price_month > 0 ? `${data.price_month.toFixed(2)} BYN / мес` : 'Входит в тарифы'}</dd>
          </div>
          <div>
            <dt>В тарифах</dt>
            <dd>{plans.length ? plans.join(' · ') : 'Только платно'}</dd>
          </div>
          <div>
            <dt>Магазинов с сервисом</dt>
            <dd>{data.usage.enabled} из {data.usage.total}</dd>
          </div>
          <div>
            <dt>Настройка</dt>
            <dd>{data.setup_route ? <code>{data.setup_route}</code> : 'Отдельного экрана нет'}</dd>
          </div>
        </dl>
      </section>

      <div className="service-detail__grid">
        <section className="panel service-detail__features">
          <div className="panel__head">
            <div>
              <h2>Все возможности</h2>
              <p className="muted">
                {data.status === 'planned'
                  ? 'Что войдёт в сервис после запуска. До готовности возможность не продаётся как работающая.'
                  : 'Полный состав функций, которые получает магазин.'}
              </p>
            </div>
          </div>
          {data.features.length ? (
            <ul className="service-features">
              {data.features.map((feature) => (
                <li key={feature}>
                  <span className="service-features__mark">•</span>
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Список возможностей для этого сервиса скоро появится.</p>
          )}
        </section>

        <aside className="service-detail__side">
          <section className="panel">
            <h3>Спрос на сервис</h3>
            <div className="service-detail__stats">
              <div>
                <span>Включён</span>
                <strong>{data.usage.enabled}</strong>
              </div>
              <div>
                <span>Всего магазинов</span>
                <strong>{data.usage.total}</strong>
              </div>
              {data.usage.revenue_month > 0 && (
                <div>
                  <span>Доход в месяц</span>
                  <strong>{data.usage.revenue_month.toFixed(2)} BYN</strong>
                </div>
              )}
            </div>
            <p className="muted service-detail__hint">
              {activeTenants.length
                ? 'Ниже — магазины, у которых сервис уже включён.'
                : 'Пока сервис не включён ни у одного магазина.'}
            </p>
          </section>

          <section className="panel">
            <h3>Зависимости</h3>
            {data.dependency_services.length ? (
              <ul className="service-detail__deps">
                {data.dependency_services.map((item) => (
                  <li key={item.code}>
                    <Link to={`/platform/catalog/${item.code}`}>{item.title}</Link>
                    <span className={`registry-badge registry-badge--${item.status}`}>{STATUS_LABEL[item.status]}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">Сервис работает самостоятельно.</p>
            )}
          </section>
        </aside>
      </div>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Магазины с этим сервисом</h2>
            <p className="muted">Кто уже включил сервис и на каком тарифе работает.</p>
          </div>
        </div>
        {data.usage.tenants.length ? (
          <div className="platform-table-wrap">
            <table className="platform-table platform-table--services">
              <thead>
                <tr>
                  <th>Магазин</th>
                  <th>Тариф</th>
                  <th>Статус сервиса</th>
                  <th>Тип</th>
                </tr>
              </thead>
              <tbody>
                {data.usage.tenants.map((tenant) => (
                  <tr key={tenant.id}>
                    <td>
                      <Link to={`/platform/tenants/${tenant.id}`}>{tenant.name}</Link>
                      <span className="muted"> / {tenant.slug}</span>
                    </td>
                    <td>{PLAN_LABEL[tenant.plan_code] ?? tenant.plan_code}</td>
                    <td>
                      <span className={`badge ${TENANT_STATUS_TONE[tenant.status] ?? 'badge--muted'}`}>
                        {TENANT_STATUS[tenant.status] ?? tenant.status}
                      </span>
                    </td>
                    <td>{tenant.is_demo ? 'Демо' : 'Клиент'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">Пока никто не включал этот сервис.</p>
        )}
      </section>

      {data.related.length > 0 && (
        <section className="service-detail__related">
          <div className="panel__head">
            <div>
              <h2>Другие сервисы группы «{data.group}»</h2>
              <p className="muted">Сравните состав и статус готовности.</p>
            </div>
          </div>
          <div className="service-related-grid">
            {data.related.map((item) => (
              <RelatedCard key={item.code} item={item} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

function RelatedCard({ item }: { item: PlatformServiceLink }) {
  return (
    <Link to={`/platform/catalog/${item.code}`} className={`panel service-related-card registry-card--${item.status}`}>
      <div>
        <strong>{item.title}</strong>
        <span className={`registry-badge registry-badge--${item.status}`}>{STATUS_LABEL[item.status]}</span>
      </div>
      <p>{item.description}</p>
    </Link>
  )
}
