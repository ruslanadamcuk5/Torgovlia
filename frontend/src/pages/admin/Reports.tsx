import { useMemo, useState } from 'react'
import { useApi } from '../../lib/useApi'
import { downloadFile } from '../../lib/api'
import { useToast } from '../../store/ToastContext'
import { Loader } from '../../components/ui'
import { Icon } from '../../components/icons'
import { formatMoney } from '../../lib/format'

interface ReportRow {
  date: string
  orders: number
  completed: number
  revenue: number
}

interface Report {
  range: { from: string; to: string; days: number }
  kpis: {
    orders: number
    completed: number
    revenue: number
    avg_check: number
    new_customers: number
    items_sold: number
    discount: number
    delivery_fee: number
    cancelled: number
  }
  daily: ReportRow[]
  statuses: { code: string; label: string; count: number }[]
  fulfillment: { pickup: number; delivery: number }
  top_products: { title: string; quantity: number; revenue: number }[]
  categories: { title: string; revenue: number }[]
}

const PERIODS = [
  { days: 7, label: '7 дней' },
  { days: 30, label: '30 дней' },
  { days: 90, label: '90 дней' },
  { days: 365, label: 'Год' },
]

const EXPORTS = [
  { kind: 'daily', label: 'По дням' },
  { kind: 'products', label: 'По товарам' },
  { kind: 'categories', label: 'По категориям' },
  { kind: 'statuses', label: 'По статусам' },
  { kind: 'orders', label: 'Все заказы' },
]

function humanDay(value: string) {
  const [, month, day] = value.split('-')
  return `${day}.${month}`
}

export default function Reports() {
  const { toast } = useToast()
  const [days, setDays] = useState(30)
  const { data, loading, error } = useApi<Report>(`/admin/reports?days=${days}`)

  const maxRevenue = useMemo(
    () => Math.max(1, ...(data?.daily ?? []).map((row) => row.revenue)),
    [data],
  )

  const exportCsv = async (kind: string) => {
    try {
      await downloadFile(
        `/admin/reports/export.csv?kind=${kind}&days=${days}`,
        `report-${kind}-${new Date().toISOString().slice(0, 10)}.csv`,
      )
      toast('CSV-файл сохранён')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось выгрузить отчёт', 'error')
    }
  }

  if (loading) return <Loader label="Считаем отчёт…" />
  if (error || !data) {
    return (
      <div className="admin-page">
        <section className="panel panel--accent">
          <h2>Не удалось загрузить отчёт</h2>
          <p>{error ?? 'Попробуйте обновить страницу.'}</p>
        </section>
      </div>
    )
  }

  const k = data.kpis
  const maxProduct = Math.max(1, ...data.top_products.map((row) => row.revenue))
  const maxCategory = Math.max(1, ...data.categories.map((row) => row.revenue))
  const totalFulfillment = Math.max(1, data.fulfillment.pickup + data.fulfillment.delivery)

  return (
    <div className="admin-page reports-page">
      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Отчёт по продажам</h2>
            <p className="muted">
              {new Date(data.range.from).toLocaleDateString('ru-BY')} — {new Date(data.range.to).toLocaleDateString('ru-BY')}.
              Выручка считается по выданным заказам, отменённые не входят.
            </p>
          </div>
          <div className="report-periods">
            {PERIODS.map((period) => (
              <button
                key={period.days}
                type="button"
                className={`btn btn--sm ${days === period.days ? 'btn--primary' : 'btn--ghost'}`}
                onClick={() => setDays(period.days)}
              >
                {period.label}
              </button>
            ))}
          </div>
        </div>

        <div className="report-kpis">
          <article className="report-kpi">
            <span>Выручка</span>
            <strong>{formatMoney(k.revenue)}</strong>
            <small>{k.completed} выданных заказов</small>
          </article>
          <article className="report-kpi">
            <span>Средний чек</span>
            <strong>{formatMoney(k.avg_check)}</strong>
            <small>по выданным заказам</small>
          </article>
          <article className="report-kpi">
            <span>Всего заказов</span>
            <strong>{k.orders}</strong>
            <small>{k.cancelled} отменено и отклонено</small>
          </article>
          <article className="report-kpi">
            <span>Новые покупатели</span>
            <strong>{k.new_customers}</strong>
            <small>впервые за период</small>
          </article>
          <article className="report-kpi">
            <span>Продано</span>
            <strong>{k.items_sold.toLocaleString('ru-BY', { maximumFractionDigits: 2 })}</strong>
            <small>кг и штук в заказах</small>
          </article>
          <article className="report-kpi">
            <span>Скидки и доставка</span>
            <strong>{formatMoney(k.discount)}</strong>
            <small>доставка {formatMoney(k.delivery_fee)}</small>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h3>Выручка по дням</h3>
            <p className="muted">Столбик — выданные заказы за день. Наведите, чтобы увидеть сумму.</p>
          </div>
        </div>
        <div className="report-chart">
          {data.daily.map((row) => (
            <div className="report-bar" key={row.date} title={`${humanDay(row.date)} · ${formatMoney(row.revenue)} · ${row.completed} выданных`}>
              <div className="report-bar__track">
                <span style={{ height: `${Math.max(row.revenue > 0 ? 3 : 0, (row.revenue / maxRevenue) * 100)}%` }} />
              </div>
              <small>{humanDay(row.date)}</small>
            </div>
          ))}
        </div>
      </section>

      <div className="report-columns">
        <section className="panel">
          <div className="panel__head"><h3>Топ товаров</h3></div>
          {data.top_products.length === 0 ? (
            <p className="muted">За период ещё нет выданных заказов.</p>
          ) : (
            <div className="report-list">
              {data.top_products.map((row, index) => (
                <div className="report-list__row" key={row.title}>
                  <span className="report-list__rank">{index + 1}</span>
                  <div className="report-list__main">
                    <div className="report-list__title">
                      <strong>{row.title}</strong>
                      <span>{formatMoney(row.revenue)}</span>
                    </div>
                    <div className="report-list__bar" style={{ width: `${(row.revenue / maxProduct) * 100}%` }} />
                    <small>{row.quantity.toLocaleString('ru-BY', { maximumFractionDigits: 2 })} ед.</small>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="panel">
          <div className="panel__head"><h3>Категории</h3></div>
          {data.categories.length === 0 ? (
            <p className="muted">Нет данных за период.</p>
          ) : (
            <div className="report-list">
              {data.categories.map((row) => (
                <div className="report-list__row" key={row.title}>
                  <div className="report-list__main">
                    <div className="report-list__title">
                      <strong>{row.title}</strong>
                      <span>{formatMoney(row.revenue)}</span>
                    </div>
                    <div className="report-list__bar" style={{ width: `${(row.revenue / maxCategory) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="report-split">
            <div>
              <span>Самовывоз</span>
              <strong>{data.fulfillment.pickup}</strong>
              <div className="report-split__bar" style={{ width: `${(data.fulfillment.pickup / totalFulfillment) * 100}%` }} />
            </div>
            <div>
              <span>Доставка</span>
              <strong>{data.fulfillment.delivery}</strong>
              <div className="report-split__bar report-split__bar--alt" style={{ width: `${(data.fulfillment.delivery / totalFulfillment) * 100}%` }} />
            </div>
          </div>
        </section>
      </div>

      <div className="report-columns">
        <section className="panel">
          <div className="panel__head"><h3>Статусы заказов</h3></div>
          <div className="report-statuses">
            {data.statuses.map((row) => (
              <div key={row.code}>
                <span>{row.label}</span>
                <strong>{row.count}</strong>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel__head">
            <div>
              <h3>Выгрузить в Excel</h3>
              <p className="muted">CSV с разделителем «;» открывается в Excel и Google Таблицах.</p>
            </div>
          </div>
          <div className="report-exports">
            {EXPORTS.map((item) => (
              <button key={item.kind} type="button" className="btn btn--outline" onClick={() => exportCsv(item.kind)}>
                <Icon name="download" size={16} /> {item.label}
              </button>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
