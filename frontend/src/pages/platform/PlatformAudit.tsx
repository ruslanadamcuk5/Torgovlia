import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { API_BASE } from '../../lib/api'
import { usePlatformApi } from '../../lib/platformApi'
import { useToast } from '../../store/ToastContext'
import { humanDate } from '../../lib/format'
import type { AuditPage, Tenant } from '../../lib/types'

const PAGE_SIZE = 50

const ACTION_LABEL: Record<string, string> = {
  'platform.login': 'Вход в платформу',
  'platform.login.failed': 'Неудачный вход',
  'platform.login.blocked': 'Вход заблокирован',
  'platform.alerts.telegram': 'Отправка алерта',
  'tenant.support.create': 'Создано обращение',
  'tenant.support.update': 'Изменено обращение',
  'tenant.provisioning.start': 'Запуск сайта',
  'tenant.lifecycle': 'Жизненный цикл',
  'tenant.impersonate': 'Вход в магазин',
  'invoice.paid': 'Счёт оплачен',
  'user.login': 'Вход в магазин',
  'user.login.failed': 'Неудачный вход в магазин',
}

function actionLabel(action: string) {
  return ACTION_LABEL[action] ?? action
}

function detailsText(details: Record<string, unknown>) {
  return Object.entries(details)
    .map(([key, value]) => `${key}=${typeof value === 'object' ? JSON.stringify(value) : String(value)}`)
    .join(' · ')
}

export default function PlatformAudit() {
  const { toast } = useToast()
  const [q, setQ] = useState('')
  const [tenantId, setTenantId] = useState('')
  const [action, setAction] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [page, setPage] = useState(0)
  const [exporting, setExporting] = useState(false)

  const { data: tenants } = usePlatformApi<{ items: Tenant[] }>('/tenants?limit=200')

  const params = useMemo(() => {
    const value = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(page * PAGE_SIZE) })
    if (q.trim()) value.set('q', q.trim())
    if (tenantId) value.set('tenant_id', tenantId)
    if (action.trim()) value.set('action', action.trim())
    if (dateFrom) value.set('date_from', dateFrom)
    if (dateTo) value.set('date_to', dateTo)
    return value
  }, [q, tenantId, action, dateFrom, dateTo, page])

  const { data, loading, error, reload } = usePlatformApi<AuditPage>(`/audit?${params}`)
  const total = data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const resetPage = () => setPage(0)

  const tenantName = (id?: number | null) =>
    tenants?.items.find((item) => item.id === id)?.name ?? (id ? `Магазин #${id}` : 'Платформа')

  const exportCsv = async () => {
    setExporting(true)
    try {
      const value = new URLSearchParams(params)
      value.delete('limit')
      value.delete('offset')
      const token = localStorage.getItem('tg_platform_token')
      const response = await fetch(`${API_BASE}/platform/audit/export?${value}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!response.ok) throw new Error('Не удалось выгрузить журнал')
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `torgovlia-audit-${new Date().toISOString().slice(0, 10)}.csv`
      link.click()
      URL.revokeObjectURL(url)
      toast('Журнал выгружен в CSV')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось выгрузить журнал', 'error')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="platform-page">
      <section className="platform-stats">
        <div className="panel"><span>Записей в выборке</span><strong>{data ? total : '—'}</strong></div>
        <div className="panel"><span>Входы в платформу</span><strong>{(data?.items ?? []).filter((item) => item.action === 'platform.login').length}</strong></div>
        <div className="panel"><span>Ошибки входа</span><strong>{(data?.items ?? []).filter((item) => item.action.endsWith('.failed') || item.action.endsWith('.blocked')).length}</strong></div>
        <div className="panel"><span>Страница</span><strong>{page + 1} <small>/ {pages}</small></strong></div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Журнал действий</h2>
            <p className="muted">Кто, что и когда сделал: входы, биллинг, запуск сайтов, поддержка и настройки.</p>
          </div>
          <button type="button" className="btn btn--sm btn--outline" disabled={exporting} onClick={() => void exportCsv()}>
            {exporting ? 'Готовим CSV…' : 'Выгрузить CSV'}
          </button>
        </div>

        <div className="audit-filters">
          <input
            className="input input--sm"
            placeholder="Поиск: телефон, действие, объект"
            value={q}
            onChange={(event) => { setQ(event.target.value); resetPage() }}
          />
          <select className="input input--sm input--select" value={tenantId} onChange={(event) => { setTenantId(event.target.value); resetPage() }}>
            <option value="">Все магазины</option>
            {tenants?.items.map((tenant) => (
              <option key={tenant.id} value={tenant.id}>{tenant.name}</option>
            ))}
          </select>
          <input
            className="input input--sm"
            placeholder="Действие: platform.login"
            value={action}
            onChange={(event) => { setAction(event.target.value); resetPage() }}
          />
          <label className="audit-filters__date">
            <span>С</span>
            <input className="input input--sm" type="date" value={dateFrom} onChange={(event) => { setDateFrom(event.target.value); resetPage() }} />
          </label>
          <label className="audit-filters__date">
            <span>По</span>
            <input className="input input--sm" type="date" value={dateTo} onChange={(event) => { setDateTo(event.target.value); resetPage() }} />
          </label>
          <button type="button" className="btn btn--sm btn--ghost" onClick={reload}>Обновить</button>
        </div>

        {error && <p className="form-error">{error}</p>}

        <div className="platform-table-wrap">
          <table className="platform-table">
            <thead>
              <tr><th>Когда</th><th>Кто</th><th>Действие</th><th>Магазин</th><th>Объект</th><th>Детали</th></tr>
            </thead>
            <tbody>
              {loading && <tr><td colSpan={6} className="muted">Загрузка…</td></tr>}
              {!loading && !(data?.items ?? []).length && (
                <tr><td colSpan={6} className="muted">Записей нет. Измените фильтры.</td></tr>
              )}
              {!loading && (data?.items ?? []).map((entry) => (
                <tr key={entry.id}>
                  <td className="audit-cell-date">{humanDate(entry.created_at)}</td>
                  <td>{entry.actor || '—'}</td>
                  <td>
                    <strong>{actionLabel(entry.action)}</strong>
                    <span className="muted audit-cell-code">{entry.action}</span>
                  </td>
                  <td>
                    {entry.tenant_id ? (
                      <Link to={`/platform/tenants/${entry.tenant_id}`}>{tenantName(entry.tenant_id)}</Link>
                    ) : 'Платформа'}
                  </td>
                  <td>{entry.entity}{entry.entity_id ? ` #${entry.entity_id}` : ''}</td>
                  <td className="audit-cell-details">{detailsText(entry.details) || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="audit-pager">
          <button type="button" className="btn btn--sm btn--ghost" disabled={page === 0 || loading} onClick={() => setPage((value) => Math.max(0, value - 1))}>
            Назад
          </button>
          <span className="muted">Записи {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} из {total}</span>
          <button type="button" className="btn btn--sm btn--ghost" disabled={page + 1 >= pages || loading} onClick={() => setPage((value) => value + 1)}>
            Вперёд
          </button>
        </div>
      </section>
    </div>
  )
}
