import { useState } from 'react'
import { Link } from 'react-router-dom'
import { platformApi, usePlatformApi } from '../../lib/platformApi'
import { useToast } from '../../store/ToastContext'
import { humanDate } from '../../lib/format'
import type { Incident, IncidentList, Tenant } from '../../lib/types'

const SEVERITY: Record<string, { label: string; badge: string }> = {
  minor: { label: 'Незначительный', badge: 'badge--muted' },
  major: { label: 'Серьёзный', badge: 'badge--gold' },
  critical: { label: 'Критический', badge: 'badge--danger' },
}

const STATUS: Record<string, { label: string; badge: string }> = {
  investigating: { label: 'Выясняем причину', badge: 'badge--danger' },
  identified: { label: 'Причина найдена', badge: 'badge--gold' },
  monitoring: { label: 'Наблюдаем', badge: 'badge--gold' },
  resolved: { label: 'Решён', badge: 'badge--fresh' },
}

const UPDATE_STATUS = [
  { value: 'investigating', label: 'Выясняем причину' },
  { value: 'identified', label: 'Причина найдена' },
  { value: 'monitoring', label: 'Наблюдаем' },
  { value: 'resolved', label: 'Решён' },
]

export default function PlatformIncidents() {
  const { toast } = useToast()
  const [state, setState] = useState('all')
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [severity, setSeverity] = useState('minor')
  const [tenantId, setTenantId] = useState('')
  const [busy, setBusy] = useState<string | null>(null)

  const { data: incidents, loading, reload } = usePlatformApi<IncidentList>(`/incidents?state=${state}&limit=200`)
  const { data: tenants } = usePlatformApi<{ items: Tenant[] }>('/tenants?limit=200')

  const activeCount = (incidents?.items ?? []).filter((item) => item.status !== 'resolved').length

  const createIncident = async () => {
    if (title.trim().length < 3) {
      toast('Укажите заголовок инцидента', 'error')
      return
    }
    setBusy('create')
    try {
      await platformApi('/incidents', {
        method: 'POST',
        body: {
          title: title.trim(),
          body: body.trim(),
          severity,
          tenant_id: tenantId ? Number(tenantId) : null,
        },
      })
      setTitle('')
      setBody('')
      setSeverity('minor')
      setTenantId('')
      toast('Инцидент открыт')
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось открыть инцидент', 'error')
    } finally {
      setBusy(null)
    }
  }

  const addUpdate = async (incident: Incident, text: string, nextStatus: string) => {
    if (text.trim().length < 2) {
      toast('Опишите, что изменилось', 'error')
      return
    }
    setBusy(`update-${incident.id}`)
    try {
      await platformApi(`/incidents/${incident.id}/updates`, {
        method: 'POST',
        body: { body: text.trim(), status: nextStatus },
      })
      toast(nextStatus === 'resolved' ? 'Инцидент закрыт' : 'Обновление добавлено')
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось добавить обновление', 'error')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="platform-page">
      <section className="platform-stats">
        <div className="panel"><span>Активные инциденты</span><strong>{activeCount}</strong></div>
        <div className="panel"><span>Всего в выборке</span><strong>{incidents?.total ?? '—'}</strong></div>
        <div className="panel"><span>Статус-страница</span><strong><Link to="/status" target="_blank">Открыть</Link></strong></div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Новый инцидент</h2>
            <p className="muted">Платформенный или по конкретному магазину. Запись сразу появляется на статус-странице.</p>
          </div>
        </div>
        <div className="incident-form">
          <input className="input input--sm" placeholder="Заголовок: например, сбой оплаты картой" value={title} maxLength={200} onChange={(event) => setTitle(event.target.value)} />
          <select className="input input--sm input--select" value={severity} onChange={(event) => setSeverity(event.target.value)}>
            {Object.entries(SEVERITY).map(([value, meta]) => <option key={value} value={value}>{meta.label}</option>)}
          </select>
          <select className="input input--sm input--select" value={tenantId} onChange={(event) => setTenantId(event.target.value)}>
            <option value="">Вся платформа</option>
            {tenants?.items.map((tenant) => <option key={tenant.id} value={tenant.id}>{tenant.name}</option>)}
          </select>
          <textarea className="input input--sm incident-form__body" placeholder="Что произошло, кого затронуло и что уже делаем" value={body} maxLength={5000} onChange={(event) => setBody(event.target.value)} />
          <button type="button" className="btn btn--sm btn--outline" disabled={busy === 'create'} onClick={() => void createIncident()}>
            Открыть инцидент
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Инциденты</h2>
            <p className="muted">Хронология обновлений видна команде и на публичной статус-странице.</p>
          </div>
          <select className="input input--sm input--select" value={state} onChange={(event) => setState(event.target.value)}>
            <option value="all">Все</option>
            <option value="active">Активные</option>
            <option value="resolved">Решённые</option>
          </select>
        </div>

        {loading && <p className="muted">Загрузка…</p>}
        {!loading && !(incidents?.items ?? []).length && <p className="muted">Инцидентов нет — это хорошо.</p>}

        <div className="incident-list">
          {(incidents?.items ?? []).map((incident) => {
            const meta = SEVERITY[incident.severity] ?? SEVERITY.minor
            const status = STATUS[incident.status] ?? STATUS.investigating
            return (
              <article key={incident.id} className={`incident ${incident.status === 'resolved' ? 'is-resolved' : ''}`}>
                <header className="incident__head">
                  <div>
                    <div className="incident__badges">
                      <span className={`badge ${meta.badge}`}>{meta.label}</span>
                      <span className={`badge ${status.badge}`}>{status.label}</span>
                    </div>
                    <h3>{incident.title}</h3>
                    <p className="muted">
                      {incident.tenant_id ? (
                        <Link to={`/platform/tenants/${incident.tenant_id}`}>{incident.tenant_name ?? `Магазин #${incident.tenant_id}`}</Link>
                      ) : 'Вся платформа'}
                      {' · '}открыт {humanDate(incident.started_at)}
                      {incident.resolved_at ? ` · решён ${humanDate(incident.resolved_at)}` : ''}
                    </p>
                  </div>
                </header>
                {incident.body && <p className="incident__body">{incident.body}</p>}
                <div className="incident__timeline">
                  {incident.updates.map((update) => (
                    <div key={update.id} className="incident-update">
                      <span className={`incident-update__dot incident-update__dot--${update.status}`} />
                      <div>
                        <strong>{STATUS[update.status]?.label ?? update.status}</strong>
                        <span className="muted"> · {update.author} · {humanDate(update.created_at)}</span>
                        <p>{update.body}</p>
                      </div>
                    </div>
                  ))}
                </div>
                <IncidentUpdateForm incident={incident} busy={busy === `update-${incident.id}`} onSubmit={addUpdate} />
              </article>
            )
          })}
        </div>
      </section>
    </div>
  )
}

function IncidentUpdateForm({
  incident,
  busy,
  onSubmit,
}: {
  incident: Incident
  busy: boolean
  onSubmit: (incident: Incident, text: string, nextStatus: string) => Promise<void>
}) {
  const [text, setText] = useState('')
  const [nextStatus, setNextStatus] = useState('monitoring')

  return (
    <div className="incident-update-form">
      <input
        className="input input--sm"
        placeholder="Что изменилось"
        value={text}
        maxLength={5000}
        onChange={(event) => setText(event.target.value)}
      />
      <select className="input input--sm input--select" value={nextStatus} onChange={(event) => setNextStatus(event.target.value)}>
        {UPDATE_STATUS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
      </select>
      <button
        type="button"
        className="btn btn--sm btn--ghost"
        disabled={busy}
        onClick={() => { void onSubmit(incident, text, nextStatus); setText('') }}
      >
        Добавить
      </button>
    </div>
  )
}
