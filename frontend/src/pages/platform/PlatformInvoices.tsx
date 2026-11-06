import { useState } from 'react'
import { Link } from 'react-router-dom'
import { platformApi, usePlatformApi } from '../../lib/platformApi'
import { useToast } from '../../store/ToastContext'
import { formatMoney, humanDate } from '../../lib/format'
import type { Invoice, Tenant } from '../../lib/types'

const STATUS_LABEL: Record<string, string> = {
  draft: 'Черновик',
  open: 'К оплате',
  paid: 'Оплачен',
  canceled: 'Отменён',
}

const KIND_LABEL: Record<string, string> = {
  subscription: 'Подписка',
  plan_change: 'Смена тарифа',
  addon: 'Сервис',
  manual: 'Прочее',
}

const STATUS_BADGE: Record<string, string> = {
  open: 'badge--gold',
  paid: 'badge--fresh',
  canceled: 'badge--muted',
  draft: 'badge--muted',
}

export default function PlatformInvoices() {
  const { toast } = useToast()
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState<number | null>(null)

  const params = new URLSearchParams({ limit: '200' })
  if (status) params.set('status', status)
  const { data: invoices, loading, reload } = usePlatformApi<Invoice[]>(`/invoices?${params}`)
  const { data: tenants } = usePlatformApi<{ items: Tenant[] }>('/tenants?limit=200')

  const tenantName = (id?: number) =>
    tenants?.items.find((item) => item.id === id)?.name ?? `Магазин #${id ?? '—'}`

  const act = async (invoice: Invoice, action: 'paid' | 'cancel') => {
    setBusy(invoice.id)
    try {
      if (action === 'paid') {
        await platformApi(`/invoices/${invoice.id}/paid`, { method: 'POST' })
        toast(`Счёт ${invoice.number} отмечен оплаченным`)
      } else {
        await platformApi(`/invoices/${invoice.id}/cancel?reason=${encodeURIComponent('Отменён платформой')}`, {
          method: 'POST',
        })
        toast(`Счёт ${invoice.number} отменён`)
      }
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить счёт', 'error')
    } finally {
      setBusy(null)
    }
  }

  const openTotal = (invoices ?? [])
    .filter((item) => item.status === 'open')
    .reduce((sum, item) => sum + item.amount, 0)

  return (
    <div className="platform-page">
      <section className="platform-stats">
        <div className="panel"><span>Всего счетов</span><strong>{invoices?.length ?? '—'}</strong></div>
        <div className="panel"><span>К оплате</span><strong>{(invoices ?? []).filter((item) => item.status === 'open').length}</strong></div>
        <div className="panel"><span>Сумма к оплате</span><strong>{formatMoney(openTotal)} <small>BYN</small></strong></div>
        <div className="panel"><span>Оплачено</span><strong>{(invoices ?? []).filter((item) => item.status === 'paid').length}</strong></div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Счета платформы</h2>
            <p className="muted">Подтверждение оплаты включает тариф и платные сервисы автоматически.</p>
          </div>
          <select className="input input--sm input--select" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">Все статусы</option>
            {Object.entries(STATUS_LABEL).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>

        <div className="platform-table-wrap">
          <table className="platform-table">
            <thead>
              <tr><th>Счёт</th><th>Магазин</th><th>Назначение</th><th>Сумма</th><th>Создан</th><th>Статус</th><th /></tr>
            </thead>
            <tbody>
              {loading && <tr><td colSpan={7} className="muted">Загрузка…</td></tr>}
              {!loading && (invoices ?? []).map((item) => (
                <tr key={item.id}>
                  <td><strong>{item.number}</strong></td>
                  <td>
                    {item.tenant_id ? (
                      <Link to={`/platform/tenants/${item.tenant_id}`}>{tenantName(item.tenant_id)}</Link>
                    ) : '—'}
                  </td>
                  <td>
                    {item.description}
                    <span className="muted"> · {KIND_LABEL[item.kind] ?? item.kind}</span>
                  </td>
                  <td>{formatMoney(item.amount)} {item.currency}</td>
                  <td>{humanDate(item.created_at)}</td>
                  <td>
                    <span className={`badge ${STATUS_BADGE[item.status] ?? 'badge--muted'}`}>
                      {STATUS_LABEL[item.status] ?? item.status}
                    </span>
                  </td>
                  <td>
                    {item.status === 'open' && (
                      <div className="platform-invoice-actions">
                        <button type="button" className="btn btn--sm btn--primary" disabled={busy === item.id} onClick={() => void act(item, 'paid')}>
                          Оплачен
                        </button>
                        <button type="button" className="btn btn--sm btn--ghost" disabled={busy === item.id} onClick={() => void act(item, 'cancel')}>
                          Отменить
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {!loading && !(invoices ?? []).length && (
                <tr><td colSpan={7} className="muted">Счетов нет.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
