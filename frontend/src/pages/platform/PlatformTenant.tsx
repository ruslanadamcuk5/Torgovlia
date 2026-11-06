import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { platformApi, usePlatformApi } from '../../lib/platformApi'
import { useToast } from '../../store/ToastContext'
import { Spinner } from '../../components/ui'
import type { ServiceItem, ServiceList, Tenant } from '../../lib/types'

const STATUS_LABEL: Record<string, string> = {
  draft: 'Черновик',
  onboarding: 'Настройка',
  active: 'Активен',
  grace: 'Отсрочка',
  suspended: 'Приостановлен',
  archived: 'Архив',
}

const SERVICE_STATUS: Record<string, string> = {
  enabled: 'Включён',
  disabled: 'Выключен',
  trial: 'Пробный',
  pending_payment: 'Ждёт оплаты',
  suspended: 'Приостановлен',
}

export default function PlatformTenant() {
  const { id } = useParams()
  const { toast } = useToast()
  const tenantId = Number(id)
  const { data: tenant, loading, reload: reloadTenant } = usePlatformApi<Tenant>(tenantId ? `/tenants/${tenantId}` : null)
  const { data: services, loading: servicesLoading, reload: reloadServices } = usePlatformApi<ServiceList>(tenantId ? `/tenants/${tenantId}/services` : null)

  const [domain, setDomain] = useState('')
  const [domainKind, setDomainKind] = useState('custom')
  const [busy, setBusy] = useState<string | null>(null)
  const [group, setGroup] = useState('all')

  const items = services?.items ?? []
  const groups = useMemo(() => {
    const seen: string[] = []
    for (const item of items) if (!seen.includes(item.group)) seen.push(item.group)
    return seen
  }, [items])
  const visible = group === 'all' ? items : items.filter((item) => item.group === group)

  const updateService = async (item: ServiceItem, patch: Record<string, unknown>) => {
    setBusy(item.code)
    try {
      await platformApi(`/tenants/${tenantId}/services/${item.code}`, { method: 'PATCH', body: patch })
      toast(`«${item.title}» обновлён`)
      reloadServices()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить сервис', 'error')
    } finally {
      setBusy(null)
    }
  }

  const updateTenant = async (patch: Record<string, unknown>) => {
    setBusy('tenant')
    try {
      await platformApi(`/tenants/${tenantId}`, { method: 'PATCH', body: patch })
      toast('Магазин обновлён')
      reloadTenant()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить', 'error')
    } finally {
      setBusy(null)
    }
  }

  const addDomain = async () => {
    if (domain.trim().length < 3) return toast('Укажите домен', 'error')
    setBusy('domain')
    try {
      await platformApi(`/tenants/${tenantId}/domains`, {
        method: 'POST',
        body: { host: domain.trim().toLowerCase(), kind: domainKind, is_primary: false },
      })
      setDomain('')
      toast('Домен добавлен. Настройте DNS по инструкции.')
      reloadTenant()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось добавить домен', 'error')
    } finally {
      setBusy(null)
    }
  }

  const removeDomain = async (domainId: number) => {
    setBusy(`domain-${domainId}`)
    try {
      await platformApi(`/tenants/${tenantId}/domains/${domainId}`, { method: 'DELETE' })
      toast('Домен отключён')
      reloadTenant()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось отключить домен', 'error')
    } finally {
      setBusy(null)
    }
  }

  if (loading || !tenant) {
    return <div className="loader-block"><Spinner /> Загружаем магазин…</div>
  }

  return (
    <div className="platform-page">
      <div className="platform-breadcrumb"><Link to="/platform/tenants">Магазины</Link> / {tenant.name}</div>

      <section className="panel platform-tenant-head">
        <div>
          <h2>{tenant.name}</h2>
          <p className="muted">/{tenant.slug} · {tenant.category_preset ?? 'без категории'} · {tenant.currency}</p>
        </div>
        <div className="platform-tenant-head__controls">
          <label className="field">
            <span className="field__label">Тариф</span>
            <select className="input input--sm input--select" value={tenant.plan_code} onChange={(event) => void updateTenant({ plan_code: event.target.value })}>
              <option value="start">Старт</option>
              <option value="business">Бизнес</option>
              <option value="pro">Про</option>
            </select>
          </label>
          <label className="field">
            <span className="field__label">Статус</span>
            <select className="input input--sm input--select" value={tenant.status} onChange={(event) => void updateTenant({ status: event.target.value })}>
              {Object.entries(STATUS_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div><h3>Домены</h3><p className="muted">Поддомен платформы и собственные адреса.</p></div>
        </div>
        <div className="platform-domains">
          {tenant.domains.map((item) => (
            <div key={item.id} className="platform-domain">
              <div>
                <strong>{item.host}</strong>
                <span className="muted">{item.kind} · SSL: {item.ssl_status} · DNS: {item.dns_status}</span>
              </div>
              {item.is_primary ? (
                <span className="badge badge--fresh">основной</span>
              ) : (
                <button type="button" className="btn btn--sm btn--danger-ghost" disabled={busy === `domain-${item.id}`} onClick={() => void removeDomain(item.id)}>
                  Отключить
                </button>
              )}
            </div>
          ))}
        </div>
        <div className="platform-domain-add">
          <input className="input input--sm" placeholder="shop.example.by" value={domain} onChange={(event) => setDomain(event.target.value)} />
          <select className="input input--sm input--select" value={domainKind} onChange={(event) => setDomainKind(event.target.value)}>
            <option value="custom">Свой домен</option>
            <option value="alias">Алиас</option>
          </select>
          <button type="button" className="btn btn--sm btn--outline" disabled={busy === 'domain'} onClick={() => void addDomain()}>Добавить</button>
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h3>Сервисы магазина</h3>
            <p className="muted">Платформа может принудительно включить сервис и заблокировать его от изменений владельцем.</p>
          </div>
        </div>

        <div className="services-tabs">
          <button type="button" className={group === 'all' ? 'is-active' : ''} onClick={() => setGroup('all')}>Все · {items.length}</button>
          {groups.map((name) => (
            <button key={name} type="button" className={group === name ? 'is-active' : ''} onClick={() => setGroup(name)}>{name}</button>
          ))}
        </div>

        {servicesLoading ? (
          <div className="loader-block"><Spinner /> Загружаем сервисы…</div>
        ) : (
          <div className="platform-service-list">
            {visible.map((item) => (
              <div key={item.code} className={`platform-service ${item.enabled ? 'is-on' : ''}`}>
                <div className="platform-service__main">
                  <strong>{item.title}</strong>
                  <span className="muted">{item.description}</span>
                  <span className="platform-service__meta">
                    {item.tier} {item.price_month > 0 ? `· ${item.price_month.toFixed(2)} BYN/мес` : ''}
                    {item.dependencies.length ? ` · зависит: ${item.dependencies.join(', ')}` : ''}
                  </span>
                </div>
                <div className="platform-service__controls">
                  <select
                    className="input input--sm input--select"
                    value={item.status}
                    disabled={busy === item.code}
                    onChange={(event) => void updateService(item, { status: event.target.value })}
                  >
                    {Object.entries(SERVICE_STATUS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                  <label className="switch-row switch-row--compact">
                    <input
                      type="checkbox"
                      checked={item.locked_by_platform}
                      disabled={busy === item.code}
                      onChange={(event) => void updateService(item, { locked_by_platform: event.target.checked })}
                    />
                    <span className="switch" />
                    <span>Заблокировать</span>
                  </label>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
