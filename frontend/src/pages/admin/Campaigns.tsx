import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Loader, Spinner } from '../../components/ui'
import { Icon } from '../../components/icons'
import { formatMoney } from '../../lib/format'

type Channel = 'email' | 'sms'
type CampaignStatus = 'draft' | 'sending' | 'sent' | 'cancelled'

interface Segment {
  code: string
  title: string
  description: string
  email: number
  sms: number
}

interface Campaign {
  id: number
  name: string
  channel: Channel
  channel_label: string
  subject: string
  body: string
  segment: string
  segment_title: string
  filters: { min_orders?: number; min_spent?: number; last_order_days?: number }
  status: CampaignStatus
  recipients_count: number
  sent_count: number
  failed_count: number
  skipped_count: number
  demo_count: number
  created_by: string
  sent_at: string | null
  created_at: string
}

interface Meta {
  segments: Segment[]
  channels: Record<string, boolean>
  demo_mode: boolean
  limits: { recipients: number; email_body: number; sms_body: number }
}

interface Recipient {
  id: number
  name: string
  contact: string
  contact_label: string
  status: string
  error: string
  sent_at: string | null
}

interface Audience {
  total: number
  sample: {
    name: string
    contact_label: string
    orders: number
    spent: number
    last_order: string | null
  }[]
}

const STATUS_LABEL: Record<CampaignStatus, string> = {
  draft: 'Черновик',
  sending: 'Отправляется',
  sent: 'Отправлено',
  cancelled: 'Отменён',
}

const RECIPIENT_LABEL: Record<string, string> = {
  pending: 'В очереди',
  sent: 'Отправлено',
  demo: 'Демо',
  failed: 'Ошибка',
  skipped: 'Пропущен',
}

const PRESETS: { title: string; subject: string; sms: string; email: string }[] = [
  {
    title: 'Скидка 10%',
    subject: 'Скидка 10% в {shop}',
    sms: '{shop}: скидка 10% на всё до воскресенья. Ждём вас!',
    email: 'Здравствуйте, {name}!\n\nНа этой неделе в {shop} скидка 10% на весь ассортимент. Загляните — мы отложим лучшее.\n\nС уважением, {shop}',
  },
  {
    title: 'Новые поступления',
    subject: 'Новинки в {shop}',
    sms: '{shop}: новое поступление уже на витрине. Приходите выбирать!',
    email: 'Здравствуйте, {name}!\n\nВ {shop} привезли новинки. Свежий выбор уже на витрине — приходите первыми.\n\n{shop}',
  },
  {
    title: 'Возвращайтесь',
    subject: 'Скучаем без вас — {shop}',
    sms: '{shop}: дарим 5% на следующий заказ. Покажите это сообщение на кассе.',
    email: 'Здравствуйте, {name}!\n\nДавно вас не было в {shop}. Дарим 5% на следующий заказ — просто покажите это письмо на кассе.\n\n{shop}',
  },
]

export default function Campaigns() {
  const { toast } = useToast()
  const { data: features, loading: featuresLoading } = useApi<{ services: Record<string, boolean> }>(
    '/admin/services/features',
  )
  const enabled = Boolean(features?.services.email_marketing || features?.services.sms_marketing)
  const segmentsEnabled = Boolean(features?.services.segments)

  const { data: meta, reload: reloadMeta } = useApi<Meta>(enabled ? '/admin/campaigns/meta' : null)
  const { data: history, reload: reloadHistory } = useApi<{ items: Campaign[]; total: number }>(
    enabled ? '/admin/campaigns?limit=30' : null,
  )

  const [draftId, setDraftId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [channel, setChannel] = useState<Channel>('email')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [segment, setSegment] = useState('all')
  const [minOrders, setMinOrders] = useState('')
  const [minSpent, setMinSpent] = useState('')
  const [lastOrderDays, setLastOrderDays] = useState('')
  const [audience, setAudience] = useState<Audience | null>(null)
  const [audienceBusy, setAudienceBusy] = useState(false)
  const [saving, setSaving] = useState(false)
  const [launching, setLaunching] = useState(false)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [recipients, setRecipients] = useState<Record<number, Recipient[]>>({})

  const channelConfigured = Boolean(meta?.channels[channel])
  const demoMode = Boolean(meta?.demo_mode)
  const limit = channel === 'sms' ? meta?.limits.sms_body ?? 480 : meta?.limits.email_body ?? 5000
  const selectedSegment = useMemo(
    () => meta?.segments.find((item) => item.code === segment),
    [meta, segment],
  )

  useEffect(() => {
    if (!enabled || !segmentsEnabled) return
    const timer = window.setTimeout(() => {
      setAudienceBusy(true)
      api<Audience>('/admin/campaigns/audience', {
        method: 'POST',
        body: {
          channel,
          segment,
          filters: {
            min_orders: Number(minOrders) || 0,
            min_spent: Number(minSpent) || 0,
            last_order_days: Number(lastOrderDays) || 0,
          },
        },
      })
        .then(setAudience)
        .catch(() => setAudience(null))
        .finally(() => setAudienceBusy(false))
    }, 350)
    return () => window.clearTimeout(timer)
  }, [enabled, segmentsEnabled, channel, segment, minOrders, minSpent, lastOrderDays])

  const resetForm = () => {
    setDraftId(null)
    setName('')
    setSubject('')
    setBody('')
    setSegment('all')
    setMinOrders('')
    setMinSpent('')
    setLastOrderDays('')
  }

  const loadDraft = (campaign: Campaign) => {
    if (campaign.status !== 'draft') {
      toast('Изменить можно только черновик', 'info')
      return
    }
    setDraftId(campaign.id)
    setName(campaign.name)
    setChannel(campaign.channel)
    setSubject(campaign.subject)
    setBody(campaign.body)
    setSegment(campaign.segment)
    setMinOrders(campaign.filters.min_orders ? String(campaign.filters.min_orders) : '')
    setMinSpent(campaign.filters.min_spent ? String(campaign.filters.min_spent) : '')
    setLastOrderDays(campaign.filters.last_order_days ? String(campaign.filters.last_order_days) : '')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const save = async (): Promise<Campaign | null> => {
    if (!body.trim()) {
      toast('Добавьте текст сообщения', 'error')
      return null
    }
    if (channel === 'sms' && body.length > limit) {
      toast(`SMS длиннее ${limit} символов`, 'error')
      return null
    }
    if (channel === 'email' && body.length > limit) {
      toast(`Письмо длиннее ${limit} символов`, 'error')
      return null
    }
    setSaving(true)
    try {
      const payload = {
        name: name.trim() || (channel === 'sms' ? 'SMS-рассылка' : 'Email-рассылка'),
        channel,
        subject: subject.trim(),
        body,
        segment,
        filters: {
          min_orders: Number(minOrders) || 0,
          min_spent: Number(minSpent) || 0,
          last_order_days: Number(lastOrderDays) || 0,
        },
      }
      const campaign = draftId
        ? await api<Campaign>(`/admin/campaigns/${draftId}`, { method: 'PATCH', body: payload })
        : await api<Campaign>('/admin/campaigns', { method: 'POST', body: payload })
      setDraftId(campaign.id)
      reloadHistory()
      toast(draftId ? 'Черновик сохранён' : 'Черновик создан')
      return campaign
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить рассылку', 'error')
      return null
    } finally {
      setSaving(false)
    }
  }

  const launch = async () => {
    if (!body.trim()) {
      toast('Добавьте текст сообщения', 'error')
      return
    }
    const count = audience?.total ?? selectedSegment?.[channel] ?? 0
    if (!count) {
      toast('В сегменте нет получателей', 'error')
      return
    }
    if (!channelConfigured && !demoMode) {
      toast('Канал не настроен — укажите SMTP или SMS-провайдера', 'error')
      return
    }
    const suffix = demoMode && !channelConfigured ? '\n\nНа демо-стенде отправка имитируется.' : ''
    if (!window.confirm(`Отправить рассылку ${count} получателям?${suffix}`)) return
    setLaunching(true)
    try {
      const campaign = await save()
      if (!campaign) return
      const launched = await api<Campaign>(`/admin/campaigns/${campaign.id}/launch`, { method: 'POST' })
      reloadHistory()
      reloadMeta()
      setExpanded(launched.id)
      void loadRecipients(launched.id)
      toast(`Рассылка запущена: ${launched.recipients_count} получателей`)
      resetForm()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось запустить рассылку', 'error')
    } finally {
      setLaunching(false)
    }
  }

  const loadRecipients = async (id: number) => {
    try {
      const data = await api<{ items: Recipient[] }>(`/admin/campaigns/${id}/recipients?limit=200`)
      setRecipients((current) => ({ ...current, [id]: data.items }))
    } catch {
      toast('Не удалось загрузить получателей', 'error')
    }
  }

  const toggleCampaign = (campaign: Campaign) => {
    const next = expanded === campaign.id ? null : campaign.id
    setExpanded(next)
    if (next && !recipients[next]) void loadRecipients(next)
  }

  const removeDraft = async (campaign: Campaign) => {
    if (!window.confirm(`Удалить「${campaign.name || 'черновик'}」?`)) return
    try {
      await api(`/admin/campaigns/${campaign.id}`, { method: 'DELETE' })
      if (draftId === campaign.id) resetForm()
      reloadHistory()
      toast('Черновик удалён')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось удалить', 'error')
    }
  }

  if (featuresLoading) return <Loader />

  if (!enabled) {
    return (
      <div className="admin-page">
        <section className="panel panel--accent">
          <div className="panel__head"><h2>Рассылки</h2></div>
          <p>
            Email- и SMS-рассылки доступны на тарифе <strong>«Про»</strong>. Соберите
            сегмент по покупкам, напишите сообщение и отправьте его клиентам.
          </p>
          <Link to="/admin/services" className="btn btn--primary">
            Перейти к сервисам <Icon name="arrow-right" size={17} />
          </Link>
        </section>
      </div>
    )
  }

  return (
    <div className="admin-page campaigns-page">
      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>{draftId ? 'Редактирование рассылки' : 'Новая рассылка'}</h2>
            <p className="muted">
              Сегмент собирается по покупкам и контактам. Перед отправкой видно, сколько
              клиентов получит сообщение.
            </p>
          </div>
          {draftId && (
            <button type="button" className="btn btn--sm btn--ghost" onClick={resetForm}>
              <Icon name="plus" size={15} /> Новая
            </button>
          )}
        </div>

        <div className="campaign-channel">
          <div className="campaign-channel__switch" role="group" aria-label="Канал рассылки">
            <button
              type="button"
              className={channel === 'email' ? 'is-active' : ''}
              onClick={() => setChannel('email')}
            >
              <Icon name="mail" size={16} /> Email
              <span>{selectedSegment?.email ?? 0}</span>
            </button>
            <button
              type="button"
              className={channel === 'sms' ? 'is-active' : ''}
              onClick={() => setChannel('sms')}
            >
              <Icon name="send" size={16} /> SMS
              <span>{selectedSegment?.sms ?? 0}</span>
            </button>
          </div>
          {!channelConfigured && (
            <div className="campaign-warning">
              {demoMode
                ? 'Канал не настроен: на демо-стенде отправка имитируется, сообщения не уходят.'
                : channel === 'email'
                  ? 'SMTP не настроен — письма не уйдут. Задайте SMTP_HOST и SMTP_FROM на сервере.'
                  : 'SMS-провайдер не подключён — задайте SMS_PROVIDER и ключи на сервере.'}
            </div>
          )}
        </div>

        <div className="campaign-grid">
          <label className="field">
            <span className="field__label">Название</span>
            <input
              className="input"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={160}
              placeholder={channel === 'sms' ? 'SMS к выходным' : 'Осенняя акция'}
            />
          </label>
          <label className="field">
            <span className="field__label">Сегмент</span>
            <select
              className="input input--select"
              value={segment}
              onChange={(event) => setSegment(event.target.value)}
              disabled={!segmentsEnabled}
            >
              {(meta?.segments ?? []).map((item) => (
                <option key={item.code} value={item.code}>
                  {item.title} · {channel === 'sms' ? item.sms : item.email}
                </option>
              ))}
            </select>
            <span className="field__hint">
              {segmentsEnabled
                ? selectedSegment?.description
                : 'Сегменты доступны на тарифе «Про» — сейчас можно писать всем клиентам.'}
            </span>
          </label>
        </div>

        {segmentsEnabled && (
          <div className="campaign-filters">
            <label className="field">
              <span className="field__label">Заказов от</span>
              <input
                className="input"
                type="number"
                min={0}
                value={minOrders}
                onChange={(event) => setMinOrders(event.target.value)}
                placeholder="0"
              />
            </label>
            <label className="field">
              <span className="field__label">Сумма от, BYN</span>
              <input
                className="input"
                type="number"
                min={0}
                value={minSpent}
                onChange={(event) => setMinSpent(event.target.value)}
                placeholder="0"
              />
            </label>
            <label className="field">
              <span className="field__label">Покупали за, дней</span>
              <input
                className="input"
                type="number"
                min={0}
                value={lastOrderDays}
                onChange={(event) => setLastOrderDays(event.target.value)}
                placeholder="без ограничения"
              />
            </label>
            <div className="campaign-audience">
              <span className="campaign-audience__label">Получателей</span>
              <strong>{audienceBusy ? '…' : audience?.total ?? 0}</strong>
              <span className="muted">из {meta?.limits.recipients ?? 1000} максимум</span>
            </div>
          </div>
        )}

        {segmentsEnabled && audience && audience.sample.length > 0 && (
          <div className="campaign-sample">
            {audience.sample.map((item) => (
              <div className="campaign-sample__row" key={item.contact_label + item.name}>
                <span className="campaign-sample__name">{item.name}</span>
                <span className="campaign-sample__contact">{item.contact_label}</span>
                <span className="muted">
                  {item.orders} заказ(ов) · {formatMoney(item.spent)}
                </span>
              </div>
            ))}
            {audience.total > audience.sample.length && (
              <span className="muted">и ещё {audience.total - audience.sample.length}…</span>
            )}
          </div>
        )}

        {channel === 'email' && (
          <label className="field campaign-subject">
            <span className="field__label">Тема письма</span>
            <input
              className="input"
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              maxLength={200}
              placeholder="Скидка 10% в {shop}"
            />
          </label>
        )}

        <div className="campaign-presets">
          <span className="muted">Шаблон:</span>
          {PRESETS.map((preset) => (
            <button
              type="button"
              key={preset.title}
              onClick={() => {
                setBody(channel === 'sms' ? preset.sms : preset.email)
                if (channel === 'email') setSubject(preset.subject)
              }}
            >
              {preset.title}
            </button>
          ))}
        </div>

        <label className="field">
          <span className="field__label">
            Текст сообщения
            <span className={body.length > limit ? 'campaign-counter is-over' : 'campaign-counter'}>
              {body.length} / {limit}
            </span>
          </span>
          <textarea
            className="textarea"
            rows={channel === 'sms' ? 4 : 9}
            value={body}
            onChange={(event) => setBody(event.target.value)}
            maxLength={channel === 'sms' ? limit : undefined}
            placeholder={'Здравствуйте, {name}! В {shop} скидка 10% до воскресенья.'}
          />
          <span className="field__hint">
            Подстановки: {'{name}'} — имя клиента, {'{shop}'} — название магазина.
          </span>
        </label>

        <div className="campaign-actions">
          <button type="button" className="btn btn--ghost" onClick={save} disabled={saving || launching}>
            {saving ? <Spinner /> : <Icon name="check" size={16} />} Сохранить черновик
          </button>
          <button type="button" className="btn btn--primary" onClick={launch} disabled={saving || launching}>
            {launching ? <Spinner /> : <Icon name="send" size={16} />} Отправить
          </button>
          <span className="muted">Отправка идёт в фоне, статистика обновится автоматически.</span>
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <h3>История рассылок</h3>
          <span className="muted">{history?.total ?? 0} кампаний</span>
        </div>
        <div className="campaign-history">
          {(history?.items ?? []).map((campaign) => (
            <div className="campaign-history__item" key={campaign.id}>
              <div className="campaign-history__row">
                <span className={`campaign-badge campaign-badge--${campaign.channel}`}>
                  {campaign.channel === 'sms' ? 'SMS' : 'Email'}
                </span>
                <div className="campaign-history__main">
                  <strong>{campaign.name || 'Без названия'}</strong>
                  <small>
                    {campaign.segment_title} · {new Date(campaign.created_at).toLocaleString('ru-BY')}
                    {campaign.created_by ? ` · ${campaign.created_by}` : ''}
                  </small>
                </div>
                <span className={`campaign-status campaign-status--${campaign.status}`}>
                  {STATUS_LABEL[campaign.status]}
                </span>
                <div className="campaign-history__stats">
                  <span>получателей {campaign.recipients_count}</span>
                  {campaign.sent_count > 0 && <span>отправлено {campaign.sent_count}</span>}
                  {campaign.demo_count > 0 && <span className="is-demo">демо {campaign.demo_count}</span>}
                  {campaign.failed_count > 0 && <span className="is-error">ошибок {campaign.failed_count}</span>}
                </div>
                <div className="campaign-history__actions">
                  {campaign.status === 'draft' && (
                    <>
                      <button type="button" className="btn btn--sm btn--ghost" onClick={() => loadDraft(campaign)}>
                        Изменить
                      </button>
                      <button type="button" className="btn btn--sm btn--ghost" onClick={() => removeDraft(campaign)}>
                        Удалить
                      </button>
                    </>
                  )}
                  <button type="button" className="btn btn--sm btn--ghost" onClick={() => toggleCampaign(campaign)}>
                    {expanded === campaign.id ? 'Скрыть' : 'Получатели'}
                  </button>
                </div>
              </div>
              {expanded === campaign.id && (
                <div className="campaign-recipients">
                  {(recipients[campaign.id] ?? []).slice(0, 100).map((recipient) => (
                    <div className="campaign-recipients__row" key={recipient.id}>
                      <span>{recipient.name}</span>
                      <span className="muted">{recipient.contact_label}</span>
                      <span className={`campaign-recipient-status campaign-recipient-status--${recipient.status}`}>
                        {RECIPIENT_LABEL[recipient.status] ?? recipient.status}
                      </span>
                      {recipient.error && <small>{recipient.error}</small>}
                    </div>
                  ))}
                  {(recipients[campaign.id] ?? []).length === 0 && (
                    <p className="muted">Получатели появятся после запуска.</p>
                  )}
                  {campaign.body && <pre className="campaign-preview-text">{campaign.body}</pre>}
                </div>
              )}
            </div>
          ))}
          {(history?.items ?? []).length === 0 && (
            <p className="muted">Рассылок ещё не было. Соберите сегмент и отправьте первую.</p>
          )}
        </div>
      </section>
    </div>
  )
}
