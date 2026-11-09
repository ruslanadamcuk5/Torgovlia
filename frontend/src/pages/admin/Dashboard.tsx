import { Link } from 'react-router-dom'
import { useSite } from '../../store/SettingsContext'
import { useApi } from '../../lib/useApi'
import { Loader } from '../../components/ui'
import { Icon, type IconName } from '../../components/icons'
import type { Onboarding, Order, Stats } from '../../lib/types'
import { formatMoney, formatQty, humanDate, statusLabel, unitShort } from '../../lib/format'

export default function Dashboard() {
  const { site } = useSite()
  const { data: stats, loading } = useApi<Stats>('/admin/stats')
  const { data: onboarding } = useApi<Onboarding>('/admin/onboarding')
  const { data: ordersData } = useApi<{ items: Order[] }>('/admin/orders?status=active&limit=6')
  const { data: audit } = useApi<{ items: { id: number; actor: string; action: string; created_at: string }[] }>('/admin/audit?limit=8')

  if (!site) return null
  const s = site.settings
  const cards: { icon: IconName; label: string; value: string; hint: string; tone?: string }[] = [
    { icon: 'list', label: 'Заказы сегодня', value: String(stats?.orders_today ?? 0), hint: `${stats?.orders_new ?? 0} новых ожидают сборки`, tone: 'gold' },
    { icon: 'check', label: 'Выручка сегодня', value: stats ? formatMoney(stats.revenue_today) : '—', hint: 'по выданным заказам' },
    { icon: 'chart', label: 'Выручка за месяц', value: stats ? formatMoney(stats.revenue_month) : '—', hint: 'с начала месяца' },
    { icon: 'wallet', label: 'Средний чек', value: stats ? formatMoney(stats.avg_order) : '—', hint: `${stats?.customers_total ?? 0} покупателей` },
  ]

  return (
    <div className="admin-page">
      <section className="admin-welcome">
        <div>
          <span className="eyebrow eyebrow--light">Магазин{s.city ? ` · ${s.city}` : ''}</span>
          <h2>Хорошего дня и удачных продаж</h2>
          <p>{s.address || [s.market_name, s.pavilion].filter(Boolean).join(', ') || 'Здесь заказы, каталог и настройки сайта.'}</p>
        </div>
        <div className="admin-welcome__actions">
          <Link to="/admin/catalog" className="btn btn--gold"><Icon name="plus" size={18} /> Добавить товар</Link>
          <Link to="/admin/orders" className="btn btn--ghost-light"><Icon name="list" size={18} /> Собрать заказы</Link>
        </div>
      </section>

      {onboarding && !onboarding.complete && (
        <section className="panel onboarding">
          <div className="onboarding__head">
            <div>
              <h2>Запуск магазина</h2>
              <p className="muted">Выполнено {onboarding.done} из {onboarding.total} шагов — осталось немного.</p>
            </div>
            <strong className="onboarding__percent">{onboarding.percent}%</strong>
          </div>
          <div className="onboarding__bar"><span style={{ width: `${onboarding.percent}%` }} /></div>
          <div className="onboarding__steps">
            {onboarding.steps.map((step) => (
              <Link key={step.code} to={step.href} className={`onboarding-step ${step.done ? 'is-done' : ''}`}>
                <span className="onboarding-step__mark">
                  <Icon name={step.done ? 'check' : 'arrow-right'} size={15} />
                </span>
                <span>
                  <strong>{step.title}</strong>
                  <small>{step.description}</small>
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {loading ? <Loader /> : (
        <div className="stat-grid">
          {cards.map((card) => (
            <div className={`stat-card ${card.tone ? `stat-card--${card.tone}` : ''}`} key={card.label}>
              <span className="stat-card__icon"><Icon name={card.icon} size={21} /></span>
              <div>
                <span className="stat-card__label">{card.label}</span>
                <strong className="stat-card__value">{card.value}</strong>
                <span className="stat-card__hint">{card.hint}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="admin-dashboard-grid">
        <section className="panel">
          <div className="panel__head">
            <h2>Заказы в работе</h2>
            <Link to="/admin/orders" className="link-arrow">Все заказы <Icon name="arrow-right" size={16} /></Link>
          </div>
          {ordersData && ordersData.items.length > 0 ? (
            <div className="dash-orders">
              {ordersData.items.map((order) => (
                <Link to="/admin/orders" className="dash-order" key={order.id}>
                  <div className="dash-order__time">
                    <strong>{order.pickup_time}</strong>
                    <span>{humanDate(order.pickup_date)}</span>
                  </div>
                  <div className="dash-order__info">
                    <strong>{order.number} · {order.customer_name}</strong>
                    <span>{order.items.map((item) => `${item.title} — ${formatQty(item.quantity)} ${unitShort(item.unit)}`).join(', ')}</span>
                  </div>
                  <div className="dash-order__sum">
                    <strong>{formatMoney(order.total_amount)}</strong>
                    <span className={`status status--${order.status === 'ready' ? 'success' : order.status === 'new' ? 'warn' : 'info'}`}>{statusLabel(order.status)}</span>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <p className="muted">Активных заказов пока нет. Новые заказы появятся здесь автоматически.</p>
          )}
        </section>

        <section className="panel">
          <div className="panel__head">
            <h2>Товары-лидеры</h2>
            <span className="muted">по сумме заказов</span>
          </div>
          {stats && stats.top_products.length > 0 ? (
            <ol className="top-list">
              {stats.top_products.map((item, index) => (
                <li key={item.title}>
                  <span className="top-list__num">{index + 1}</span>
                  <div><strong>{item.title}</strong><span>{formatQty(item.quantity)} продано</span></div>
                  <b>{formatMoney(item.revenue)}</b>
                </li>
              ))}
            </ol>
          ) : (
            <p className="muted">Статистика появится после первых заказов.</p>
          )}
        </section>

        <section className="panel">
          <div className="panel__head">
            <h2>Состояние каталога</h2>
            <Link to="/admin/catalog" className="link-arrow">Открыть <Icon name="arrow-right" size={16} /></Link>
          </div>
          <div className="catalog-health">
            <div><span>Активных товаров</span><strong>{stats?.products_active ?? 0}</strong></div>
            <div><span>Нет в наличии</span><strong className="text-warn">{stats?.products_out_of_stock ?? 0}</strong></div>
            <div><span>Всего пользователей</span><strong>{stats?.users_total ?? 0}</strong></div>
            <div><span>Всего заказов</span><strong>{stats?.orders_total ?? 0}</strong></div>
          </div>
          <Link to="/admin/catalog" className="btn btn--outline btn--block">Управлять каталогом</Link>
        </section>

        <section className="panel">
          <div className="panel__head">
            <h2>Последние действия</h2>
            <span className="muted">журнал</span>
          </div>
          {audit && audit.items.length > 0 ? (
            <ul className="audit-list">
              {audit.items.map((row) => (
                <li key={row.id}>
                  <span className="audit-list__dot" />
                  <div><strong>{row.action}</strong><span>{row.actor || 'система'} · {new Date(row.created_at).toLocaleString('ru-BY')}</span></div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Журнал пока пуст.</p>
          )}
        </section>
      </div>

      <section className="panel panel--quick">
        <h2>Быстрые действия</h2>
        <div className="quick-actions">
          <Link to="/admin/catalog"><Icon name="plus" size={22} /><span>Добавить товар</span></Link>
          <Link to="/admin/orders"><Icon name="list" size={22} /><span>Список заказов</span></Link>
          <Link to="/admin/promotions"><Icon name="percent" size={22} /><span>Настроить акции</span></Link>
          <Link to="/admin/qr"><Icon name="qr" size={22} /><span>Скачать QR-коды</span></Link>
          <Link to="/admin/users"><Icon name="users" size={22} /><span>Роли и доступы</span></Link>
          <Link to="/admin/settings"><Icon name="settings" size={22} /><span>Реквизиты и сайт</span></Link>
        </div>
      </section>
    </div>
  )
}
