import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Icon } from '../../components/icons'
import { Loader } from '../../components/ui'
import type { ServiceDetail, ServiceLink } from '../../lib/types'

const TIER_LABEL: Record<string, string> = {
  free: 'Базовый',
  start: 'Старт',
  business: 'Бизнес',
  pro: 'Про',
  addon: 'Платный сервис',
  platform: 'Только платформа',
}

const STATUS_LABEL: Record<string, string> = {
  enabled: 'Включён',
  disabled: 'Выключен',
  trial: 'Пробный период',
  pending_payment: 'Ждёт оплаты',
  suspended: 'Приостановлен',
}

const READINESS: Record<string, { label: string; tone: string }> = {
  ready: { label: 'Работает', tone: 'fresh' },
  partial: { label: 'Частично', tone: 'muted' },
  planned: { label: 'Скоро', tone: 'muted' },
}

export default function AdminServiceDetail() {
  const { code = '' } = useParams()
  const { toast } = useToast()
  const { data, loading, error, reload } = useApi<ServiceDetail>(code ? `/admin/services/${code}` : null)
  const [busy, setBusy] = useState(false)

  const toggle = async () => {
    if (!data) return
    setBusy(true)
    try {
      await api(`/admin/services/${data.code}/${data.enabled ? 'disable' : 'enable'}`, {
        method: 'POST',
      })
      toast(data.enabled ? `«${data.title}» выключен` : `«${data.title}» включён`)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить сервис', 'error')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <Loader label="Загружаем сервис" />
  if (error || !data) {
    return (
      <div className="empty-state">
        <div className="empty-state__icon"><Icon name="alert" size={26} /></div>
        <h3>Сервис не найден</h3>
        <p>{error ?? 'Возможно, он больше не подключён к платформе.'}</p>
        <Link to="/admin/services" className="btn btn--primary">Все сервисы</Link>
      </div>
    )
  }

  const paid = data.tier === 'addon' && data.price_month > 0
  const readiness = READINESS[data.readiness ?? 'ready'] ?? READINESS.ready
  const statusSteps = [
    { title: 'Сервис включён', status: data.enabled ? 'done' : 'current' },
    { title: 'Зависимости готовы', status: data.dependency_services.every((item) => item.enabled) ? 'done' : 'todo' },
    { title: data.setup_route ? 'Настроить магазин' : 'Настроек не требуется', status: data.setup_route ? 'todo' : 'done' },
  ] as const

  return (
    <div className="service-detail">
      <Link to="/admin/services" className="detail-back">← Все сервисы</Link>

      <section className="panel service-detail__hero">
        <div className="service-detail__intro">
          <span className="service-card__group">{data.group}</span>
          <h1>{data.title}</h1>
          <div className="service-detail__badges">
            <span className={`badge ${data.enabled ? 'badge--fresh' : 'badge--muted'}`}>
              {STATUS_LABEL[data.status] ?? data.status}
            </span>
            <span className={`badge badge--${readiness.tone}`}>{readiness.label}</span>
            {data.locked_by_platform && <span className="badge badge--muted"><Icon name="lock" size={12} /> Платформа</span>}
            {paid && <span className="service-tier service-tier--addon">{data.price_month.toFixed(2)} BYN / мес</span>}
          </div>
          <p className="service-detail__about">{data.about}</p>
          {data.audience && (
            <p className="service-detail__audience"><Icon name="users" size={15} /> {data.audience}</p>
          )}
          <div className="service-detail__actions">
            {data.enabled && data.setup_route && (
              <Link to={data.setup_route} className="btn btn--primary btn--sm">
                <Icon name="settings" size={15} /> Перейти к настройке
              </Link>
            )}
            {data.locked_by_platform ? (
              <span className="service-card__locked"><Icon name="lock" size={14} /> Управляется платформой</span>
            ) : data.enabled ? (
              <button
                type="button"
                className="btn btn--sm btn--outline"
                disabled={!data.can_disable || busy}
                onClick={() => void toggle()}
              >
                {busy ? 'Сохраняем…' : 'Выключить сервис'}
              </button>
            ) : (
              <button
                type="button"
                className="btn btn--sm btn--primary"
                disabled={!data.can_enable || busy}
                onClick={() => void toggle()}
              >
                {busy ? 'Сохраняем…' : paid ? 'Подключить' : 'Включить сервис'}
              </button>
            )}
          </div>
        </div>

        <dl className="service-detail__facts">
          <div>
            <dt>Тариф</dt>
            <dd>{TIER_LABEL[data.tier] ?? data.tier}</dd>
          </div>
          <div>
            <dt>Цена</dt>
            <dd>{paid ? `${data.price_month.toFixed(2)} BYN / мес` : 'Включено в тариф'}</dd>
          </div>
          <div>
            <dt>Пробный период</dt>
            <dd>{data.trial_days > 0 ? `${data.trial_days} дней` : 'Нет'}</dd>
          </div>
          <div>
            <dt>Зависимости</dt>
            <dd>{data.dependency_services.length ? `${data.dependency_services.length}` : 'Не нужны'}</dd>
          </div>
          <div>
            <dt>Код сервиса</dt>
            <dd><code>{data.code}</code></dd>
          </div>
        </dl>
      </section>

      <div className="service-detail__grid">
        <section className="panel service-detail__features">
          <div className="panel__head">
            <div>
              <h2>Что умеет сервис</h2>
              <p className="muted">
                {data.readiness === 'planned'
                  ? 'Полный набор возможностей после запуска. Статус и сроки видны в карточке готовности.'
                  : 'Все возможности, которые получает магазин после включения.'}
              </p>
            </div>
          </div>
          {data.features.length ? (
            <ul className="service-features">
              {data.features.map((feature) => (
                <li key={feature}>
                  <Icon name="check" size={15} />
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Подробный список возможностей для этого сервиса скоро появится.</p>
          )}
        </section>

        <aside className="service-detail__side">
          <section className="panel">
            <h3>Готовность</h3>
            <p className={`service-detail__readiness service-detail__readiness--${data.readiness ?? 'ready'}`}>
              <strong>{readiness.label}</strong>
              {data.readiness_note ? ` — ${data.readiness_note}` : data.readiness === 'ready' ? ' — сервис работает на витрине и в админке.' : ''}
            </p>
          </section>

          <section className="panel">
            <h3>Как начать</h3>
            <ol className="service-steps">
              {statusSteps.map((step) => (
                <li key={step.title} className={`is-${step.status}`}>
                  <span className="service-steps__dot" />
                  <span>{step.title}</span>
                </li>
              ))}
            </ol>
          </section>

          <section className="panel">
            <h3>Зависимости</h3>
            {data.dependency_services.length ? (
              <ul className="service-detail__deps">
                {data.dependency_services.map((item) => (
                  <li key={item.code}>
                    <Link to={`/admin/services/${item.code}`}>{item.title}</Link>
                    <span className={`badge ${item.enabled ? 'badge--fresh' : 'badge--muted'}`}>
                      {item.enabled ? 'Включён' : 'Выключен'}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">Сервис работает самостоятельно.</p>
            )}
            {data.included_in_plan && <p className="service-included"><Icon name="check" size={13} /> Входит в текущий тариф</p>}
          </section>
        </aside>
      </div>

      {data.related.length > 0 && (
        <section className="service-detail__related">
          <div className="panel__head">
            <div>
              <h2>Другие сервисы группы «{data.group}»</h2>
              <p className="muted">Часто включают вместе или вместо этого сервиса.</p>
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

function RelatedCard({ item }: { item: ServiceLink }) {
  const readiness = READINESS[item.readiness] ?? READINESS.ready
  return (
    <Link to={`/admin/services/${item.code}`} className="panel service-related-card">
      <div>
        <strong>{item.title}</strong>
        <span className={`badge badge--${readiness.tone}`}>{readiness.label}</span>
      </div>
      <p>{item.description}</p>
    </Link>
  )
}
