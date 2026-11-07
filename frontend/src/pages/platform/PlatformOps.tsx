import { useState } from 'react'
import { Link } from 'react-router-dom'
import { platformApi, usePlatformApi } from '../../lib/platformApi'
import { useToast } from '../../store/ToastContext'
import type { AlertsDigest, AlertSendResult, OpsOverview, TenantHealth, UptimeRunResult } from '../../lib/types'

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
      <td>
        {item.uptime?.uptime_24h != null ? (
          <span className={`badge ${item.uptime.uptime_24h >= 99 ? 'badge--fresh' : item.uptime.uptime_24h >= 95 ? 'badge--gold' : 'badge--danger'}`}>
            {item.uptime.uptime_24h}%
          </span>
        ) : (
          <span className="muted">—</span>
        )}
      </td>
      <td className="oc-num">
        {item.uptime?.avg_latency_ms != null ? `${item.uptime.avg_latency_ms} мс` : '—'}
      </td>
      <td>
        {item.uptime?.last_checked_at ? (
          <span className={`badge ${item.uptime.last_ok ? 'badge--fresh' : 'badge--danger'}`}>
            {item.uptime.last_ok ? 'Отвечает' : 'Не отвечает'}
          </span>
        ) : (
          <span className="muted">Нет проверок</span>
        )}
      </td>
    </tr>
  )
}

export default function PlatformOps() {
  const { data, loading, error, reload } = usePlatformApi<OpsOverview>('/ops/overview')
  const { data: alerts, reload: reloadAlerts } = usePlatformApi<AlertsDigest>('/alerts')
  const { toast } = useToast()
  const [sending, setSending] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)

  const runChecks = async () => {
    setChecking(true)
    try {
      const result = await platformApi<UptimeRunResult>('/ops/checks', { method: 'POST' })
      toast(`Проверено сайтов: ${result.checked}. Отвечают: ${result.ok}, ошибок: ${result.failed}`)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось проверить сайты', 'error')
    } finally {
      setChecking(false)
    }
  }

  const sendAlerts = async (test: boolean) => {
    setSending(test ? 'test' : 'digest')
    try {
      const result = await platformApi<AlertSendResult>('/alerts/telegram', {
        method: 'POST',
        body: { test },
      })
      toast(result.message)
      reloadAlerts()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось отправить сводку', 'error')
    } finally {
      setSending(null)
    }
  }

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
            <h2>Оповещения</h2>
            <p className="muted">Сводка ошибок, SSL, DNS и долгов. Отправка в Telegram — вручную или по cron.</p>
          </div>
          <span className={`badge ${alerts?.telegram_configured ? 'badge--fresh' : 'badge--muted'}`}>
            {alerts?.telegram_configured ? 'Telegram подключён' : 'Telegram не настроен'}
          </span>
        </div>

        <div className="platform-alerts">
          <div className="platform-alerts__stats">
            <div><span>Ошибки</span><strong>{alerts?.errors ?? 0}</strong></div>
            <div><span>Предупреждения</span><strong>{alerts?.warnings ?? 0}</strong></div>
            <div><span>Всего</span><strong>{alerts?.total ?? 0}</strong></div>
          </div>
          <pre className="platform-alerts__preview">{alerts?.text ?? 'Загрузка…'}</pre>
          <div className="platform-alerts__actions">
            <button
              type="button"
              className="btn btn--sm btn--primary"
              disabled={!alerts?.telegram_configured || sending !== null}
              onClick={() => void sendAlerts(false)}
            >
              {sending === 'digest' ? 'Отправляем…' : 'Отправить сводку'}
            </button>
            <button
              type="button"
              className="btn btn--sm btn--outline"
              disabled={!alerts?.telegram_configured || sending !== null}
              onClick={() => void sendAlerts(true)}
            >
              {sending === 'test' ? 'Отправляем…' : 'Тестовое сообщение'}
            </button>
            <Link to="/platform/tenants" className="btn btn--sm btn--ghost">К магазинам</Link>
          </div>
          {!alerts?.telegram_configured && (
            <p className="muted">
              Задайте <code>TELEGRAM_BOT_TOKEN</code> и <code>TELEGRAM_CHAT_ID</code> в <code>backend/.env</code>,
              затем перезапустите сайт.
            </p>
          )}
        </div>
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
            <p className="muted">Публикация, домен, доступность за 24 часа и задержка ответа.</p>
          </div>
          <button
            type="button"
            className="btn btn--sm btn--outline"
            disabled={checking}
            onClick={() => void runChecks()}
          >
            {checking ? 'Проверяем…' : 'Проверить сейчас'}
          </button>
        </div>
        <div className="platform-table-wrap">
          <table className="platform-table">
            <thead>
              <tr><th>Магазин</th><th>Домен</th><th>Публикация</th><th>Состояние</th><th>Запуск</th><th>SSL</th><th>Доступность</th><th>Задержка</th><th>Проверка</th></tr>
            </thead>
            <tbody>
              {(data?.items ?? []).map((item) => <SiteRow key={item.tenant_id} item={item} />)}
              {!(data?.items ?? []).length && (
                <tr><td colSpan={9} className="muted">Магазинов пока нет.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
