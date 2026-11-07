import { Link } from 'react-router-dom'
import { usePlatformApi } from '../../lib/platformApi'
import type { OpsOverview, TenantHealth } from '../../lib/types'

const DEPLOY_LABEL: Record<string, string> = {
  not_started: 'Не запускался',
  queued: 'В очереди',
  in_progress: 'Публикуется',
  deployed: 'Работает',
  failed: 'Ошибка',
  paused: 'Приостановлен',
}

const DEPLOY_BADGE: Record<string, string> = {
  deployed: 'badge--fresh',
  queued: 'badge--gold',
  in_progress: 'badge--gold',
  failed: 'badge--danger',
  paused: 'badge--muted',
  not_started: 'badge--muted',
}

const LEVEL_LABEL: Record<string, string> = {
  ok: 'В порядке',
  attention: 'Требует внимания',
  error: 'Проблема',
}

const LEVEL_BADGE: Record<string, string> = {
  ok: 'badge--fresh',
  attention: 'badge--gold',
  error: 'badge--danger',
}

function DeployBadge({ status }: { status: string }) {
  return (
    <span className={`badge ${DEPLOY_BADGE[status] ?? 'badge--muted'}`}>
      {DEPLOY_LABEL[status] ?? status}
    </span>
  )
}

function SiteRow({ item }: { item: TenantHealth }) {
  return (
    <tr>
      <td>
        <Link to={`/platform/tenants/${item.tenant_id}`}><strong>{item.name}</strong></Link>
        <span className="muted"> /{item.slug}</span>
      </td>
      <td>{item.primary_host || '—'}</td>
      <td><DeployBadge status={item.deploy_status} /></td>
      <td>
        <span className={`badge ${LEVEL_BADGE[item.level] ?? 'badge--muted'}`}>
          {LEVEL_LABEL[item.level] ?? item.level}
        </span>
      </td>
      <td>
        {item.job_id ? (
          <div className="ops-progress">
            <span className="ops-progress__bar"><span style={{ width: `${item.job_progress}%` }} /></span>
            <small>{item.job_progress}%</small>
          </div>
        ) : (
          <span className="muted">—</span>
        )}
      </td>
      <td>{item.ssl_status === 'active' || item.ssl_status === 'issued' ? 'HTTPS' : item.ssl_status}</td>
    </tr>
  )
}

export default function PlatformOps() {
  const { data, loading, error, reload } = usePlatformApi<OpsOverview>('/ops/overview')

  if (error) {
    return (
      <div className="empty-state">
        <h3>Не удалось загрузить мониторинг</h3>
        <p>{error}</p>
        <button type="button" className="btn btn--primary" onClick={reload}>Повторить</button>
      </div>
    )
  }

  return (
    <div className="platform-page">
      <section className="platform-stats">
        <div className="panel"><span>Сайтов</span><strong>{data?.tenants_total ?? '—'}</strong></div>
        <div className="panel"><span>Работают</span><strong>{data?.deployed ?? '—'}</strong></div>
        <div className="panel"><span>В очереди запуска</span><strong>{data?.queue_total ?? '—'}</strong></div>
        <div className="panel"><span>Требуют внимания</span><strong>{data?.attention_total ?? '—'}</strong></div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Очередь запусков</h2>
            <p className="muted">Магазины, которые проходят провижининг: хостинг, домен, SSL, публикация.</p>
          </div>
          <Link to="/platform/tenants" className="btn btn--sm btn--outline">Все магазины</Link>
        </div>

        {loading ? (
          <div className="muted">Загрузка…</div>
        ) : (
          <div className="ops-queue">
            {(data?.queue ?? []).map((item) => (
              <Link key={item.tenant_id} to={`/platform/tenants/${item.tenant_id}`} className="ops-queue__item">
                <div>
                  <strong>{item.name}</strong>
                  <span className="muted">/{item.slug} · {item.primary_host || 'домен не задан'}</span>
                </div>
                <div className="ops-queue__progress">
                  <span className="ops-progress__bar"><span style={{ width: `${item.job_progress}%` }} /></span>
                  <small>{item.job_progress}%</small>
                </div>
                <DeployBadge status={item.deploy_status} />
              </Link>
            ))}
            {!(data?.queue ?? []).length && <p className="muted">Очередь пуста — все сайты запущены.</p>}
          </div>
        )}
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Требуют внимания</h2>
            <p className="muted">SSL, DNS, неоплаченные счета и ошибки публикации.</p>
          </div>
          <span className="badge badge--gold">{data?.attention_total ?? 0}</span>
        </div>

        <div className="ops-attention">
          {(data?.attention ?? []).map((item) => (
            <Link key={item.tenant_id} to={`/platform/tenants/${item.tenant_id}`} className={`ops-attention__item is-${item.level}`}>
              <div>
                <strong>{item.name}</strong>
                <span className="muted">/{item.slug}</span>
              </div>
              <div className="ops-attention__issues">
                {item.issues.map((issue) => <span key={issue} className="ops-issue">{issue}</span>)}
              </div>
            </Link>
          ))}
          {!(data?.attention ?? []).length && <p className="muted">Всё в порядке — замечаний нет.</p>}
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Все сайты</h2>
            <p className="muted">Статус публикации, домен, SSL и прогресс запуска.</p>
          </div>
        </div>
        <div className="platform-table-wrap">
          <table className="platform-table">
            <thead>
              <tr><th>Магазин</th><th>Домен</th><th>Публикация</th><th>Состояние</th><th>Запуск</th><th>SSL</th></tr>
            </thead>
            <tbody>
              {(data?.items ?? []).map((item) => <SiteRow key={item.tenant_id} item={item} />)}
              {!(data?.items ?? []).length && (
                <tr><td colSpan={6} className="muted">Магазинов пока нет.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
