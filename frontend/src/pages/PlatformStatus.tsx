import { useEffect, useState } from 'react'
import { API_BASE } from '../lib/api'
import { humanDate } from '../lib/format'
import type { StatusPage } from '../lib/types'

const OVERALL = {
  operational: { label: 'Все системы работают', tone: 'ok', text: 'Сбоев нет. Магазины и оплата доступны.' },
  degraded: { label: 'Есть ограничения', tone: 'warn', text: 'Часть функций может работать медленнее или с ошибками.' },
  outage: { label: 'Крупный сбой', tone: 'bad', text: 'Мы знаем о проблеме и работаем над восстановлением.' },
}

const STATUS_LABEL: Record<string, string> = {
  investigating: 'Выясняем причину',
  identified: 'Причина найдена',
  monitoring: 'Наблюдаем',
  resolved: 'Решён',
}

const SEVERITY_LABEL: Record<string, string> = {
  minor: 'Незначительный',
  major: 'Серьёзный',
  critical: 'Критический',
}

export default function PlatformStatus() {
  const [data, setData] = useState<StatusPage | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch(`${API_BASE}/status`)
      .then((response) => {
        if (!response.ok) throw new Error('Статус временно недоступен')
        return response.json() as Promise<StatusPage>
      })
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : 'Статус временно недоступен'))
  }, [])

  const overall = OVERALL[data?.overall ?? 'operational']

  return (
    <main className="status-page">
      <div className="status-shell">
        <div className="status-brand">
          <span className="platform-logo platform-logo--sm">T</span>
          <div><strong>{data?.brand_name ?? 'Torgovlia'}</strong><span>Статус платформы</span></div>
        </div>

        {error && <div className="status-hero status-hero--bad"><strong>{error}</strong><p>Обновите страницу через минуту.</p></div>}

        {!data && !error && <div className="loader-block">Проверяем состояние…</div>}

        {data && (
          <>
            {data.maintenance_notice && (
              <div className="status-notice">
                <strong>Объявление</strong>
                <p>{data.maintenance_notice}</p>
              </div>
            )}
            <section className={`status-hero status-hero--${overall.tone}`}>
              <span className="status-dot" />
              <div>
                <strong>{overall.label}</strong>
                <p>{overall.text}</p>
                <small>Обновлено {humanDate(data.updated_at)}</small>
              </div>
            </section>

            <section className="status-section">
              <h2>Активные инциденты</h2>
              {!data.active.length && <p className="muted">Сейчас активных инцидентов нет.</p>}
              {data.active.map((incident) => (
                <article key={incident.id} className="status-incident">
                  <div className="status-incident__head">
                    <strong>{incident.title}</strong>
                    <span className={`badge ${incident.severity === 'critical' ? 'badge--danger' : incident.severity === 'major' ? 'badge--gold' : 'badge--muted'}`}>
                      {SEVERITY_LABEL[incident.severity] ?? incident.severity}
                    </span>
                  </div>
                  {incident.body && <p>{incident.body}</p>}
                  <div className="status-timeline">
                    {incident.updates.map((update) => (
                      <div key={update.id} className="status-update">
                        <span>{STATUS_LABEL[update.status] ?? update.status}</span>
                        <small>{humanDate(update.created_at)}</small>
                        <p>{update.body}</p>
                      </div>
                    ))}
                  </div>
                </article>
              ))}
            </section>

            <section className="status-section">
              <h2>История за 14 дней</h2>
              {!data.resolved.length && <p className="muted">Решённых инцидентов за период нет.</p>}
              {data.resolved.map((incident) => (
                <article key={incident.id} className="status-incident status-incident--resolved">
                  <div className="status-incident__head">
                    <strong>{incident.title}</strong>
                    <span className="badge badge--fresh">Решён</span>
                  </div>
                  <p className="muted">{humanDate(incident.started_at)} — {incident.resolved_at ? humanDate(incident.resolved_at) : '—'}</p>
                </article>
              ))}
            </section>
          </>
        )}
      </div>
    </main>
  )
}
