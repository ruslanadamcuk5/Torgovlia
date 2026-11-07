import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { platformApi, usePlatformApi } from '../../lib/platformApi'
import { useToast } from '../../store/ToastContext'
import { Spinner } from '../../components/ui'
import { formatMoney, humanDate } from '../../lib/format'
import { storefrontUrl } from '../../lib/host'
import type { ImpersonationResult, Invoice, LifecycleState, ProvisioningState, ServiceItem, ServiceList, SupportTicket, Tenant } from '../../lib/types'

const STATUS_LABEL: Record<string, string> = {
  draft: 'Черновик',
  onboarding: 'Настройка',
  active: 'Активен',
  grace: 'Отсрочка',
  suspended: 'Приостановлен',
  archived: 'Архив',
}

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

const STEP_LABEL: Record<string, string> = {
  pending: 'Ожидает',
  in_progress: 'В работе',
  done: 'Готово',
  blocked: 'Проблема',
  skipped: 'Пропущен',
}

const STEP_BADGE: Record<string, string> = {
  done: 'badge--fresh',
  in_progress: 'badge--gold',
  blocked: 'badge--danger',
  skipped: 'badge--muted',
  pending: 'badge--muted',
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
  const { data: invoices, reload: reloadInvoices } = usePlatformApi<Invoice[]>(tenantId ? `/tenants/${tenantId}/invoices` : null)
  const { data: provisioning, reload: reloadProvisioning } = usePlatformApi<ProvisioningState>(tenantId ? `/tenants/${tenantId}/provisioning` : null)
  const { data: lifecycle, reload: reloadLifecycle } = usePlatformApi<LifecycleState>(tenantId ? `/tenants/${tenantId}/lifecycle` : null)
  const { data: tickets, reload: reloadTickets } = usePlatformApi<SupportTicket[]>(tenantId ? `/tenants/${tenantId}/support` : null)

  const [domain, setDomain] = useState('')
  const [hosting, setHosting] = useState({
    hosting_provider: '',
    hosting_tariff: '',
    hosting_account: '',
    deploy_url: '',
    deploy_status: 'not_started',
    ops_note: '',
  })
  const [jobNote, setJobNote] = useState('')
  const [lifecycleReason, setLifecycleReason] = useState('')
  const [ticketSubject, setTicketSubject] = useState('')
  const [ticketBody, setTicketBody] = useState('')
  const [ticketPriority, setTicketPriority] = useState('normal')
  const [stepBusy, setStepBusy] = useState<string | null>(null)
  const [invoiceAmount, setInvoiceAmount] = useState('')
  const [invoiceDescription, setInvoiceDescription] = useState('')
  const [domainKind, setDomainKind] = useState('custom')
  const [busy, setBusy] = useState<string | null>(null)
  const [group, setGroup] = useState('all')

  useEffect(() => {
    if (!provisioning?.hosting) return
    setHosting({
      hosting_provider: provisioning.hosting.hosting_provider,
      hosting_tariff: provisioning.hosting.hosting_tariff,
      hosting_account: provisioning.hosting.hosting_account,
      deploy_url: provisioning.hosting.deploy_url,
      deploy_status: provisioning.hosting.deploy_status,
      ops_note: provisioning.hosting.ops_note,
    })
  }, [provisioning])

  useEffect(() => {
    setJobNote(provisioning?.job?.note ?? '')
  }, [provisioning?.job?.id, provisioning?.job?.note])

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
      reloadLifecycle()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить', 'error')
    } finally {
      setBusy(null)
    }
  }

  const runLifecycle = async (action: string) => {
    if (lifecycleReason.trim().length < 3) {
      toast('Укажите причину действия — она попадёт в аудит', 'error')
      return
    }
    setBusy(`lifecycle-${action}`)
    try {
      await platformApi(`/tenants/${tenantId}/lifecycle`, {
        method: 'POST',
        body: { action, reason: lifecycleReason.trim() },
      })
      toast('Статус магазина изменён')
      setLifecycleReason('')
      reloadTenant()
      reloadLifecycle()
      reloadProvisioning()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить статус', 'error')
    } finally {
      setBusy(null)
    }
  }

  const impersonate = async () => {
    if (lifecycleReason.trim().length < 3) {
      toast('Укажите причину входа — она попадёт в аудит', 'error')
      return
    }
    setBusy('impersonate')
    try {
      const result = await platformApi<ImpersonationResult>(`/tenants/${tenantId}/impersonate`, {
        method: 'POST',
        body: { reason: lifecycleReason.trim() },
      })
      const url = storefrontUrl(
        result.tenant_slug,
        result.host,
        `/login#impersonate=${encodeURIComponent(result.access_token)}`,
      )
      window.open(url, '_blank', 'noopener')
      toast(`Открыт вход в магазин как ${result.user.full_name}. Токен действует 30 минут.`)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось войти в магазин', 'error')
    } finally {
      setBusy(null)
    }
  }

  const createTicket = async () => {
    if (ticketSubject.trim().length < 2) {
      toast('Укажите тему обращения', 'error')
      return
    }
    setBusy('ticket')
    try {
      await platformApi(`/tenants/${tenantId}/support`, {
        method: 'POST',
        body: {
          subject: ticketSubject.trim(),
          body: ticketBody.trim(),
          priority: ticketPriority,
        },
      })
      setTicketSubject('')
      setTicketBody('')
      setTicketPriority('normal')
      toast('Обращение добавлено')
      reloadTickets()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось добавить обращение', 'error')
    } finally {
      setBusy(null)
    }
  }

  const toggleTicket = async (ticket: SupportTicket) => {
    setBusy(`ticket-${ticket.id}`)
    try {
      await platformApi(`/support/${ticket.id}`, {
        method: 'PATCH',
        body: { status: ticket.status === 'open' ? 'closed' : 'open' },
      })
      toast(ticket.status === 'open' ? 'Обращение закрыто' : 'Обращение открыто')
      reloadTickets()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить обращение', 'error')
    } finally {
      setBusy(null)
    }
  }

  const openStorefront = () => {
    if (!tenant) return
    const host = tenant.domains?.find((item) => item.is_primary)?.host
      ?? tenant.domains?.[0]?.host
      ?? `${tenant.slug}.localhost`
    window.open(storefrontUrl(tenant.slug, host), '_blank', 'noopener')
  }

  const saveHosting = async () => {
    setBusy('hosting')
    try {
      await platformApi(`/tenants/${tenantId}/hosting`, { method: 'PATCH', body: hosting })
      toast('Хостинг сохранён')
      reloadProvisioning()
      reloadTenant()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить хостинг', 'error')
    } finally {
      setBusy(null)
    }
  }

  const startLaunch = async () => {
    setBusy('launch')
    try {
      await platformApi(`/tenants/${tenantId}/provisioning`, { method: 'POST' })
      toast('Магазин поставлен в очередь запуска')
      reloadProvisioning()
      reloadTenant()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось создать задачу', 'error')
    } finally {
      setBusy(null)
    }
  }

  const setStep = async (jobId: number, code: string, status: string) => {
    setStepBusy(`${jobId}-${code}`)
    try {
      await platformApi(`/provisioning/${jobId}/steps/${code}`, {
        method: 'PATCH',
        body: { status },
      })
      reloadProvisioning()
      reloadTenant()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось обновить шаг', 'error')
    } finally {
      setStepBusy(null)
    }
  }

  const saveJobNote = async (jobId: number) => {
    setBusy('job-note')
    try {
      await platformApi(`/provisioning/${jobId}`, { method: 'PATCH', body: { note: jobNote } })
      toast('Заметка сохранена')
      reloadProvisioning()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить заметку', 'error')
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

  const createInvoice = async () => {
    const amount = Number(invoiceAmount.replace(',', '.'))
    if (!Number.isFinite(amount) || amount <= 0) return toast('Укажите сумму счёта', 'error')
    if (invoiceDescription.trim().length < 2) return toast('Укажите назначение платежа', 'error')
    setBusy('invoice')
    try {
      await platformApi(`/tenants/${tenantId}/invoices`, {
        method: 'POST',
        body: {
          kind: 'manual',
          amount,
          description: invoiceDescription.trim(),
          due_days: 14,
        },
      })
      setInvoiceAmount('')
      setInvoiceDescription('')
      toast('Счёт выставлен')
      reloadInvoices()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось выставить счёт', 'error')
    } finally {
      setBusy(null)
    }
  }

  const invoiceAction = async (invoice: Invoice, action: 'paid' | 'cancel') => {
    setBusy(`invoice-${invoice.id}`)
    try {
      if (action === 'paid') {
        await platformApi(`/invoices/${invoice.id}/paid`, { method: 'POST' })
        toast(`Счёт ${invoice.number} оплачен`)
      } else {
        await platformApi(`/invoices/${invoice.id}/cancel?reason=${encodeURIComponent('Отменён платформой')}`, { method: 'POST' })
        toast(`Счёт ${invoice.number} отменён`)
      }
      reloadInvoices()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить счёт', 'error')
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
          <div>
            <h3>Жизненный цикл</h3>
            <p className="muted">Приостановка, архив и восстановление с причиной; все действия — в аудите.</p>
          </div>
          <span className="badge badge--muted">{STATUS_LABEL[lifecycle?.status ?? tenant.status] ?? tenant.status}</span>
        </div>

        <div className="lifecycle">
          <div className="lifecycle__reason">
            <label className="field">
              <span className="field__label">Причина действия</span>
              <input
                className="input input--sm"
                value={lifecycleReason}
                onChange={(event) => setLifecycleReason(event.target.value)}
                placeholder="Например: не оплачен счёт или клиент закрыл магазин"
                maxLength={300}
              />
            </label>
            <button type="button" className="btn btn--sm btn--ghost" onClick={openStorefront}>
              Открыть витрину
            </button>
            <button type="button" className="btn btn--sm btn--outline" disabled={busy === 'impersonate'} onClick={() => void impersonate()}>
              Войти в магазин
            </button>
          </div>

          <div className="lifecycle__actions">
            {(lifecycle?.actions ?? [
              { action: 'suspend', label: 'Приостановить', enabled: tenant.status !== 'suspended' },
              { action: 'resume', label: 'Возобновить', enabled: tenant.status === 'suspended' },
              { action: 'archive', label: 'Архивировать', enabled: tenant.status !== 'archived' },
              { action: 'restore', label: 'Восстановить', enabled: tenant.status === 'archived' },
            ]).map((item) => (
              <button
                key={item.action}
                type="button"
                className={`btn btn--sm ${item.action === 'suspend' || item.action === 'archive' ? 'btn--danger-ghost' : 'btn--ghost'}`}
                disabled={!item.enabled || busy === `lifecycle-${item.action}`}
                onClick={() => void runLifecycle(item.action)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h3>Хостинг и запуск</h3>
            <p className="muted">Ручной режим hoster.by: аккаунт, тариф, публикация и чек-лист запуска.</p>
          </div>
          <span className={`badge ${DEPLOY_BADGE[provisioning?.hosting.deploy_status ?? tenant.deploy_status] ?? 'badge--muted'}`}>
            {provisioning?.hosting.deploy_status_label ?? DEPLOY_LABEL[tenant.deploy_status] ?? tenant.deploy_status}
          </span>
        </div>

        <div className="ops-hosting">
          <div className="ops-hosting__meta">
            <div><span className="muted">Основной домен</span><strong>{provisioning?.hosting.primary_host || '—'}</strong></div>
            <div><span className="muted">SSL</span><strong>{provisioning?.hosting.ssl_status || '—'}</strong></div>
            <div><span className="muted">DNS</span><strong>{provisioning?.hosting.dns_status || '—'}</strong></div>
            <div><span className="muted">Адрес сайта</span><strong>{provisioning?.hosting.deploy_url || '—'}</strong></div>
          </div>

          <div className="ops-hosting__form">
            <label className="field">
              <span className="field__label">Провайдер</span>
              <select className="input input--sm input--select" value={hosting.hosting_provider} onChange={(event) => setHosting({ ...hosting, hosting_provider: event.target.value })}>
                <option value="">Не выбран</option>
                <option value="hoster_by">hoster.by</option>
                <option value="other">Другой</option>
              </select>
            </label>
            <label className="field">
              <span className="field__label">Тариф хостинга</span>
              <input className="input input--sm" value={hosting.hosting_tariff} onChange={(event) => setHosting({ ...hosting, hosting_tariff: event.target.value })} placeholder="Хостинг Старт" />
            </label>
            <label className="field">
              <span className="field__label">Аккаунт</span>
              <input className="input input--sm" value={hosting.hosting_account} onChange={(event) => setHosting({ ...hosting, hosting_account: event.target.value })} placeholder="Логин или номер договора" />
            </label>
            <label className="field">
              <span className="field__label">Статус публикации</span>
              <select className="input input--sm input--select" value={hosting.deploy_status} onChange={(event) => setHosting({ ...hosting, deploy_status: event.target.value })}>
                {Object.entries(DEPLOY_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label className="field ops-hosting__wide">
              <span className="field__label">Адрес сайта</span>
              <input className="input input--sm" value={hosting.deploy_url} onChange={(event) => setHosting({ ...hosting, deploy_url: event.target.value })} placeholder="https://shop.torgovlia.by" />
            </label>
            <label className="field ops-hosting__wide">
              <span className="field__label">Заметка по эксплуатации</span>
              <textarea className="input input--sm" rows={2} value={hosting.ops_note} onChange={(event) => setHosting({ ...hosting, ops_note: event.target.value })} placeholder="Что сделано, что ждём" />
            </label>
            <button type="button" className="btn btn--sm btn--primary" disabled={busy === 'hosting'} onClick={() => void saveHosting()}>
              Сохранить хостинг
            </button>
          </div>
        </div>

        <div className="ops-launch">
          <div className="ops-launch__head">
            <div>
              <strong>Чек-лист запуска</strong>
              <span className="muted">
                {provisioning?.job
                  ? `${provisioning.job.status_label} · ${provisioning.job.steps_done} из ${provisioning.job.steps_total} шагов`
                  : 'Задача ещё не создана'}
              </span>
            </div>
            {provisioning?.job ? (
              <div className="ops-progress ops-progress--lg">
                <span className="ops-progress__bar"><span style={{ width: `${provisioning.job.progress}%` }} /></span>
                <small>{provisioning.job.progress}%</small>
              </div>
            ) : (
              <button type="button" className="btn btn--sm btn--primary" disabled={busy === 'launch'} onClick={() => void startLaunch()}>
                Поставить в очередь запуска
              </button>
            )}
          </div>

          {provisioning?.job && (
            <>
              <ol className="ops-steps">
                {provisioning.job.steps.map((step, index) => (
                  <li key={step.code} className={`ops-step is-${step.status}`}>
                    <span className="ops-step__num">{index + 1}</span>
                    <div className="ops-step__main">
                      <strong>{step.title}</strong>
                      <span className="muted">{step.detail}</span>
                      {step.note && <em className="ops-step__note">{step.note}</em>}
                    </div>
                    <span className={`badge ${STEP_BADGE[step.status] ?? 'badge--muted'}`}>
                      {STEP_LABEL[step.status] ?? step.status}
                    </span>
                    <div className="ops-step__actions">
                      {step.status !== 'done' && (
                        <button type="button" className="btn btn--sm btn--outline" disabled={stepBusy === `${provisioning.job!.id}-${step.code}`} onClick={() => void setStep(provisioning.job!.id, step.code, 'done')}>
                          Готово
                        </button>
                      )}
                      {step.status !== 'in_progress' && step.status !== 'done' && (
                        <button type="button" className="btn btn--sm btn--ghost" disabled={stepBusy === `${provisioning.job!.id}-${step.code}`} onClick={() => void setStep(provisioning.job!.id, step.code, 'in_progress')}>
                          В работе
                        </button>
                      )}
                      {step.status !== 'blocked' && step.status !== 'done' && (
                        <button type="button" className="btn btn--sm btn--danger-ghost" disabled={stepBusy === `${provisioning.job!.id}-${step.code}`} onClick={() => void setStep(provisioning.job!.id, step.code, 'blocked')}>
                          Проблема
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ol>

              <div className="ops-job-note">
                <input className="input input--sm" value={jobNote} onChange={(event) => setJobNote(event.target.value)} placeholder="Комментарий к задаче запуска" />
                <button type="button" className="btn btn--sm btn--ghost" disabled={busy === 'job-note'} onClick={() => void saveJobNote(provisioning.job!.id)}>
                  Сохранить заметку
                </button>
                {provisioning.job.status === 'done' && (
                  <button type="button" className="btn btn--sm btn--outline" disabled={busy === 'launch'} onClick={() => void startLaunch()}>
                    Новый запуск
                  </button>
                )}
              </div>
            </>
          )}
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
            <h3>Поддержка</h3>
            <p className="muted">Обращения и внутренние заметки по магазину; всё попадает в аудит.</p>
          </div>
          <span className="badge badge--gold">{(tickets ?? []).filter((item) => item.status === 'open').length} открыто</span>
        </div>

        <div className="support-ticket-form">
          <input
            className="input input--sm"
            placeholder="Тема: например, не приходит SMS"
            value={ticketSubject}
            maxLength={200}
            onChange={(event) => setTicketSubject(event.target.value)}
          />
          <select className="input input--sm input--select" value={ticketPriority} onChange={(event) => setTicketPriority(event.target.value)}>
            <option value="low">Низкий</option>
            <option value="normal">Обычный</option>
            <option value="high">Высокий</option>
          </select>
          <textarea
            className="input input--sm support-ticket-form__body"
            placeholder="Что случилось и что уже проверили"
            value={ticketBody}
            maxLength={5000}
            onChange={(event) => setTicketBody(event.target.value)}
          />
          <button type="button" className="btn btn--sm btn--outline" disabled={busy === 'ticket'} onClick={() => void createTicket()}>
            Добавить обращение
          </button>
        </div>

        <div className="support-ticket-list">
          {(tickets ?? []).map((ticket) => (
            <div key={ticket.id} className={`support-ticket ${ticket.status === 'closed' ? 'is-closed' : ''}`}>
              <div className="support-ticket__main">
                <strong>{ticket.subject}</strong>
                <span className="muted">{ticket.author} · {humanDate(ticket.created_at)} · {ticket.priority}</span>
                {ticket.body && <p>{ticket.body}</p>}
              </div>
              <div className="support-ticket__actions">
                <span className={`badge ${ticket.status === 'open' ? 'badge--gold' : 'badge--muted'}`}>
                  {ticket.status === 'open' ? 'Открыто' : 'Закрыто'}
                </span>
                <button
                  type="button"
                  className="btn btn--sm btn--ghost"
                  disabled={busy === `ticket-${ticket.id}`}
                  onClick={() => void toggleTicket(ticket)}
                >
                  {ticket.status === 'open' ? 'Закрыть' : 'Открыть'}
                </button>
              </div>
            </div>
          ))}
          {!(tickets ?? []).length && <p className="muted">Обращений пока нет.</p>}
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h3>Счета и оплата</h3>
            <p className="muted">Оплата подтверждается вручную; тариф и сервисы включаются автоматически.</p>
          </div>
          <span className="badge badge--muted">{(invoices ?? []).filter((item) => item.status === 'open').length} к оплате</span>
        </div>

        <div className="platform-table-wrap">
          <table className="platform-table">
            <thead>
              <tr><th>Номер</th><th>Назначение</th><th>Сумма</th><th>Создан</th><th>Статус</th><th /></tr>
            </thead>
            <tbody>
              {(invoices ?? []).map((item) => (
                <tr key={item.id}>
                  <td><strong>{item.number}</strong></td>
                  <td>{item.description}</td>
                  <td>{formatMoney(item.amount)} {item.currency}</td>
                  <td>{humanDate(item.created_at)}</td>
                  <td>
                    <span className={`badge ${item.status === 'paid' ? 'badge--fresh' : item.status === 'open' ? 'badge--gold' : 'badge--muted'}`}>
                      {item.status === 'paid' ? 'Оплачен' : item.status === 'open' ? 'К оплате' : item.status === 'canceled' ? 'Отменён' : item.status}
                    </span>
                  </td>
                  <td>
                    {item.status === 'open' && (
                      <div className="platform-invoice-actions">
                        <button type="button" className="btn btn--sm btn--primary" disabled={busy === `invoice-${item.id}`} onClick={() => void invoiceAction(item, 'paid')}>Оплачен</button>
                        <button type="button" className="btn btn--sm btn--ghost" disabled={busy === `invoice-${item.id}`} onClick={() => void invoiceAction(item, 'cancel')}>Отменить</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {!(invoices ?? []).length && (
                <tr><td colSpan={6} className="muted">Счетов пока нет.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="platform-invoice-create">
          <input className="input input--sm" placeholder="Сумма, BYN" value={invoiceAmount} onChange={(event) => setInvoiceAmount(event.target.value)} />
          <input className="input input--sm" placeholder="Назначение платежа" value={invoiceDescription} onChange={(event) => setInvoiceDescription(event.target.value)} />
          <button type="button" className="btn btn--sm btn--outline" disabled={busy === 'invoice'} onClick={() => void createInvoice()}>
            Выставить счёт
          </button>
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
