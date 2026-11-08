import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Icon } from '../../components/icons'
import { Loader } from '../../components/ui'
import type { ServiceItem, ServiceList, ServiceTier } from '../../lib/types'

const PLAN_LABEL: Record<string, string> = {
  start: 'Старт',
  business: 'Бизнес',
  pro: 'Про',
}

const TIER_LABEL: Record<ServiceTier, string> = {
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

export default function AdminServices() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const { data, loading, error, reload } = useApi<ServiceList>('/admin/services')
  const [busy, setBusy] = useState<string | null>(null)
  const [group, setGroup] = useState('all')

  const items = data?.items ?? []
  const groups = useMemo(() => {
    const seen: string[] = []
    for (const item of items) if (!seen.includes(item.group)) seen.push(item.group)
    return seen
  }, [items])

  const visible = group === 'all' ? items : items.filter((item) => item.group === group)
  const enabledCount = items.filter((item) => item.enabled).length

  const toggle = async (item: ServiceItem) => {
    setBusy(item.code)
    try {
      await api(`/admin/services/${item.code}/${item.enabled ? 'disable' : 'enable'}`, {
        method: 'POST',
      })
      toast(item.enabled ? `«${item.title}» выключен` : `«${item.title}» включён`)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить сервис', 'error')
    } finally {
      setBusy(null)
    }
  }

  if (loading) return <Loader label="Загружаем сервисы" />
  if (error) {
    return (
      <div className="empty-state">
        <div className="empty-state__icon"><Icon name="alert" size={26} /></div>
        <h3>Не удалось загрузить сервисы</h3>
        <p>{error}</p>
        <button type="button" className="btn btn--primary" onClick={reload}>Повторить</button>
      </div>
    )
  }

  return (
    <div className="services-page">
      <section className="panel services-summary">
        <div>
          <span className="muted">Текущий тариф</span>
          <strong>{PLAN_LABEL[data?.plan_code ?? ''] ?? data?.plan_code ?? '—'}</strong>
        </div>
        <div>
          <span className="muted">Включено сервисов</span>
          <strong>{enabledCount} из {items.length}</strong>
        </div>
        <div>
          <span className="muted">Платные сервисы</span>
          <strong>{items.filter((item) => item.tier === 'addon').length}</strong>
        </div>
        <p className="services-summary__hint">
          Полный каталог платформы. Включайте и выключайте сервисы сами — платформа
          видит те же настройки и может заблокировать обязательные.
        </p>
      </section>

      <div className="services-tabs" role="tablist">
        <button type="button" className={group === 'all' ? 'is-active' : ''} onClick={() => setGroup('all')}>
          Все · {items.length}
        </button>
        {groups.map((name) => (
          <button key={name} type="button" className={group === name ? 'is-active' : ''} onClick={() => setGroup(name)}>
            {name}
          </button>
        ))}
      </div>

      <div className="services-grid">
        {visible.map((item) => {
          const paid = item.tier === 'addon' && item.price_month > 0
          return (
            <article
              key={item.code}
              className={`service-card service-card--clickable ${item.enabled ? 'is-on' : ''} ${item.locked_by_platform ? 'is-locked' : ''}`}
              onClick={(event) => {
                if ((event.target as HTMLElement).closest('a, button')) return
                navigate(`/admin/services/${item.code}`)
              }}
            >
              <header>
                <div>
                  <h3><Link to={`/admin/services/${item.code}`}>{item.title}</Link></h3>
                  <span className="service-card__group">{item.group}</span>
                </div>
                {item.locked_by_platform ? (
                  <span className="badge badge--muted"><Icon name="lock" size={12} /> Платформа</span>
                ) : (
                  <span className={`badge ${item.enabled ? 'badge--fresh' : 'badge--muted'}`}>
                    {STATUS_LABEL[item.status] ?? item.status}
                  </span>
                )}
                {item.readiness && (
                  <span className={`badge badge--${READINESS[item.readiness]?.tone ?? 'muted'}`}>
                    {READINESS[item.readiness]?.label ?? item.readiness_title}
                  </span>
                )}
              </header>

              <p>{item.description}</p>
              {item.readiness_note && <p className="service-card__note">{item.readiness_note}</p>}

              <div className="service-card__meta">
                <span className={`service-tier service-tier--${item.tier}`}>
                  {paid ? `${item.price_month.toFixed(2)} BYN / мес` : TIER_LABEL[item.tier]}
                </span>
                {item.included_in_plan && <span className="service-included"><Icon name="check" size={13} /> В тарифе</span>}
                {item.trial_days > 0 && !item.enabled && <span className="service-trial">{item.trial_days} дней бесплатно</span>}
              </div>

              {item.dependencies.length > 0 && (
                <p className="service-card__deps">
                  Зависит от: {item.dependencies.join(', ')}
                </p>
              )}

              <footer>
                <Link to={`/admin/services/${item.code}`} className="btn btn--sm btn--ghost">
                  <Icon name="info" size={14} /> Подробнее
                </Link>
                {item.enabled && item.setup_route && (
                  <Link to={item.setup_route} className="btn btn--sm btn--ghost">
                    <Icon name="settings" size={14} /> Настроить
                  </Link>
                )}
                {item.locked_by_platform ? (
                  <span className="service-card__locked"><Icon name="lock" size={14} /> Управляется платформой</span>
                ) : item.enabled ? (
                  <button
                    type="button"
                    className="btn btn--sm btn--outline"
                    disabled={!item.can_disable || busy === item.code}
                    onClick={() => void toggle(item)}
                  >
                    {busy === item.code ? 'Сохраняем…' : 'Выключить'}
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn btn--sm btn--primary"
                    disabled={!item.can_enable || busy === item.code}
                    onClick={() => void toggle(item)}
                  >
                    {busy === item.code ? 'Сохраняем…' : paid ? 'Подключить' : 'Включить'}
                  </button>
                )}
              </footer>
            </article>
          )
        })}
      </div>
    </div>
  )
}
