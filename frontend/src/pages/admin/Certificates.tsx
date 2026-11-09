import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Icon } from '../../components/icons'
import { EmptyState, Loader, Modal } from '../../components/ui'
import { formatMoney } from '../../lib/format'
import type { GiftCertificate, GiftListResponse } from '../../lib/types'

const FILTERS = [
  { code: 'all', title: 'Все' },
  { code: 'active', title: 'Активные' },
  { code: 'pending', title: 'Ждут оплаты' },
  { code: 'used', title: 'Использованные' },
  { code: 'expired', title: 'Истёкшие' },
  { code: 'cancelled', title: 'Отменённые' },
] as const

const STATUS_TONE: Record<string, string> = {
  pending: 'gold',
  active: 'fresh',
  used: 'muted',
  expired: 'danger',
  cancelled: 'muted',
}

const PRESETS = [50, 75, 100, 150, 200]

type Form = {
  amount: string
  recipient_name: string
  recipient_phone: string
  recipient_email: string
  sender_name: string
  sender_phone: string
  message: string
  note: string
  expires_at: string
  activate: boolean
}

const EMPTY_FORM: Form = {
  amount: '100',
  recipient_name: '',
  recipient_phone: '',
  recipient_email: '',
  sender_name: '',
  sender_phone: '',
  message: '',
  note: '',
  expires_at: '',
  activate: true,
}

function shortDate(value: string | null): string {
  if (!value) return ''
  return new Date(value).toLocaleDateString('ru-BY', { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function Certificates() {
  const { toast } = useToast()
  const features = useApi<{ services: Record<string, boolean> }>('/admin/services/features')
  const enabled = features.data?.services.gift_certificates === true
  const { data, loading, error, reload } = useApi<GiftListResponse>(
    enabled ? '/admin/certificates' : null,
  )

  const [filter, setFilter] = useState<string>('all')
  const [query, setQuery] = useState('')
  const [form, setForm] = useState<Form>(EMPTY_FORM)
  const [busy, setBusy] = useState(false)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)

  const items = data?.items ?? []
  const summary = data?.summary

  const visible = useMemo(() => {
    const term = query.trim().toLowerCase()
    return items.filter((cert) => {
      if (filter !== 'all' && cert.status !== filter) return false
      if (!term) return true
      return `${cert.code} ${cert.recipient_name} ${cert.recipient_phone} ${cert.recipient_email} ${cert.sender_name}`
        .toLowerCase()
        .includes(term)
    })
  }, [items, filter, query])

  const issue = async () => {
    const amount = Number(form.amount)
    if (!Number.isFinite(amount) || amount < 1) {
      toast('Укажите сумму сертификата', 'error')
      return
    }
    if (!form.recipient_name.trim()) {
      toast('Укажите имя получателя', 'error')
      return
    }
    setBusy(true)
    try {
      await api('/admin/certificates', {
        method: 'POST',
        body: {
          amount,
          recipient_name: form.recipient_name.trim(),
          recipient_phone: form.recipient_phone.trim(),
          recipient_email: form.recipient_email.trim() || null,
          sender_name: form.sender_name.trim(),
          sender_phone: form.sender_phone.trim(),
          message: form.message.trim(),
          note: form.note.trim(),
          expires_at: form.expires_at || undefined,
          activate: form.activate,
        },
      })
      toast(form.activate ? 'Сертификат выпущен' : 'Заявка на сертификат создана')
      setForm(EMPTY_FORM)
      setShowForm(false)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось выпустить сертификат', 'error')
    } finally {
      setBusy(false)
    }
  }

  const patch = async (cert: GiftCertificate, body: Record<string, unknown>, message: string) => {
    setBusy(true)
    try {
      await api(`/admin/certificates/${cert.id}`, { method: 'PATCH', body })
      toast(message)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось обновить сертификат', 'error')
    } finally {
      setBusy(false)
    }
  }

  const copy = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code)
      toast('Код скопирован')
    } catch {
      toast(`Код: ${code}`, 'info')
    }
  }

  if (features.loading) return <Loader label="Проверяем сервис" />

  if (!enabled) {
    return (
      <div className="empty-state">
        <div className="empty-state__icon"><Icon name="gift" size={26} /></div>
        <h3>Подарочные сертификаты не подключены</h3>
        <p>Включите сервис, чтобы выпускать сертификаты и принимать их как оплату.</p>
        <Link to="/admin/services/gift_certificates" className="btn btn--primary">Открыть сервис</Link>
      </div>
    )
  }

  if (loading) return <Loader label="Загружаем сертификаты" />
  if (error) {
    return (
      <div className="empty-state">
        <div className="empty-state__icon"><Icon name="alert" size={26} /></div>
        <h3>Не удалось загрузить сертификаты</h3>
        <p>{error}</p>
        <button type="button" className="btn btn--primary" onClick={reload}>Повторить</button>
      </div>
    )
  }

  return (
    <div className="gift-page">
      <section className="gift-stats">
        <div className="panel gift-stat">
          <span>Активные</span>
          <strong>{summary?.active ?? 0}</strong>
          <small>можно принять в оплату</small>
        </div>
        <div className="panel gift-stat">
          <span>Не погашено</span>
          <strong>{formatMoney(summary?.outstanding ?? 0)}</strong>
          <small>остаток на активных</small>
        </div>
        <div className="panel gift-stat">
          <span>Погашено</span>
          <strong>{formatMoney(summary?.redeemed ?? 0)}</strong>
          <small>оплачено сертификатами</small>
        </div>
        <div className={`panel gift-stat ${(summary?.pending ?? 0) > 0 ? 'is-warn' : ''}`}>
          <span>Ждут оплаты</span>
          <strong>{summary?.pending ?? 0}</strong>
          <small>заявки с витрины</small>
        </div>
      </section>

      <div className="gift-layout">
        <section className="panel gift-board">
          <div className="gift-toolbar">
            <div className="services-tabs">
              {FILTERS.map((item) => (
                <button
                  key={item.code}
                  type="button"
                  className={filter === item.code ? 'is-active' : ''}
                  onClick={() => setFilter(item.code)}
                >
                  {item.title}
                </button>
              ))}
            </div>
            <div className="gift-toolbar__row">
              <input
                className="input"
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Код, получатель, телефон"
              />
              <button type="button" className="btn btn--primary" onClick={() => setShowForm((value) => !value)}>
                <Icon name="plus" size={16} /> Выпустить
              </button>
            </div>
          </div>

          {visible.length ? (
            <div className="gift-list">
              {visible.map((cert) => (
                <article className={`gift-card gift-card--${cert.status}`} key={cert.id}>
                  <div className="gift-card__main">
                    <div className="gift-card__head">
                      <button type="button" className="gift-code" onClick={() => void copy(cert.code)} title="Скопировать код">
                        <Icon name="gift" size={16} />
                        <span>{cert.code}</span>
                        <Icon name="tag" size={13} />
                      </button>
                      <span className={`badge badge--${STATUS_TONE[cert.status] ?? 'muted'}`}>{cert.status_label}</span>
                    </div>
                    <div className="gift-card__amounts">
                      <strong>{formatMoney(cert.balance)}</strong>
                      <span>из {formatMoney(cert.initial_amount)}</span>
                    </div>
                    <div className="gift-card__meta">
                      <span><Icon name="user" size={13} /> {cert.recipient_name || 'Без имени'}</span>
                      {(cert.recipient_phone || cert.recipient_email) && (
                        <span>{cert.recipient_phone || cert.recipient_email}</span>
                      )}
                      {cert.expires_at && <span><Icon name="calendar" size={13} /> до {shortDate(cert.expires_at)}</span>}
                    </div>
                    {cert.message && <p>«{cert.message}»</p>}
                  </div>

                  <div className="gift-card__actions">
                    {cert.status === 'pending' && (
                      <button type="button" className="btn btn--sm btn--primary" disabled={busy} onClick={() => void patch(cert, { status: 'active' }, 'Сертификат активирован')}>
                        <Icon name="check" size={14} /> Активировать
                      </button>
                    )}
                    {['pending', 'active'].includes(cert.status) && (
                      <button type="button" className="btn btn--sm btn--outline" disabled={busy} onClick={() => void patch(cert, { status: 'cancelled' }, 'Сертификат отменён')}>
                        Отменить
                      </button>
                    )}
                    {(cert.transactions.length > 0 || cert.note) && (
                      <button type="button" className="btn btn--sm btn--ghost" onClick={() => setExpanded(expanded === cert.id ? null : cert.id)}>
                        {expanded === cert.id ? 'Скрыть' : 'История'}
                      </button>
                    )}
                  </div>

                  {expanded === cert.id && (
                    <div className="gift-card__history">
                      {cert.note && <p className="gift-card__note">{cert.note}</p>}
                      {cert.transactions.map((tx) => (
                        <div className="gift-tx" key={tx.id}>
                          <span>{tx.note || tx.kind}</span>
                          <b className={tx.amount < 0 ? 'is-minus' : 'is-plus'}>
                            {tx.amount > 0 ? '+' : ''}{formatMoney(tx.amount)}
                          </b>
                          <small>{shortDate(tx.created_at)} · остаток {formatMoney(tx.balance_after)}</small>
                        </div>
                      ))}
                    </div>
                  )}
                </article>
              ))}
            </div>
          ) : (
            <EmptyState icon="gift" title="Сертификатов нет" text="Измените фильтр или выпустите первый сертификат." />
          )}
        </section>

        <aside className="panel gift-side">
          <div className="panel__head">
            <div>
              <h2>Выпуск сертификата</h2>
              <p className="muted">Код создаётся автоматически. Срок — 12 месяцев.</p>
            </div>
          </div>
          <div className="gift-presets">
            {PRESETS.map((value) => (
              <button
                key={value}
                type="button"
                className={Number(form.amount) === value ? 'is-active' : ''}
                onClick={() => setForm({ ...form, amount: String(value) })}
              >
                {value} BYN
              </button>
            ))}
          </div>
          <label className="field">
            <span className="field__label">Сумма, BYN</span>
            <input className="input" type="number" min={1} max={5000} value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} />
          </label>
          <label className="field">
            <span className="field__label">Получатель</span>
            <input className="input" value={form.recipient_name} onChange={(event) => setForm({ ...form, recipient_name: event.target.value })} placeholder="Имя получателя" maxLength={120} />
          </label>
          <div className="gift-form__row">
            <label className="field">
              <span className="field__label">Телефон</span>
              <input className="input" value={form.recipient_phone} onChange={(event) => setForm({ ...form, recipient_phone: event.target.value })} placeholder="+375…" />
            </label>
            <label className="field">
              <span className="field__label">Email</span>
              <input className="input" type="email" value={form.recipient_email} onChange={(event) => setForm({ ...form, recipient_email: event.target.value })} placeholder="необязательно" />
            </label>
          </div>
          <label className="field">
            <span className="field__label">Пожелание</span>
            <textarea className="textarea" rows={2} value={form.message} onChange={(event) => setForm({ ...form, message: event.target.value })} placeholder="Текст на открытке" maxLength={400} />
          </label>
          <div className="gift-form__row">
            <label className="field">
              <span className="field__label">Дата действия</span>
              <input className="input" type="date" value={form.expires_at} onChange={(event) => setForm({ ...form, expires_at: event.target.value })} />
            </label>
            <label className="field">
              <span className="field__label">Заметка</span>
              <input className="input" value={form.note} onChange={(event) => setForm({ ...form, note: event.target.value })} placeholder="Для себя" />
            </label>
          </div>
          <label className="gift-check">
            <input type="checkbox" checked={form.activate} onChange={(event) => setForm({ ...form, activate: event.target.checked })} />
            <span>
              <strong>Оплата уже получена</strong>
              <small>Сертификат сразу станет активным. Если выключить — попадёт в «Ждут оплаты».</small>
            </span>
          </label>
          <button type="button" className="btn btn--primary" disabled={busy} onClick={() => void issue()}>
            <Icon name="gift" size={16} /> {busy ? 'Сохраняем…' : form.activate ? 'Выпустить сертификат' : 'Создать заявку'}
          </button>
          <button type="button" className="btn btn--outline" onClick={() => { setForm(EMPTY_FORM); setShowForm(false) }}>
            Сбросить
          </button>
          <p className="gift-side__hint">
            Покупатель проверяет баланс и применяет код на странице <Link to="/gift">«Подарочные сертификаты»</Link>.
          </p>
        </aside>
      </div>

      {showForm && (
        <Modal
          title="Выпуск сертификата"
          subtitle="Короткая форма — на телефоне удобнее"
          onClose={() => setShowForm(false)}
          footer={(
            <>
              <button type="button" className="btn btn--ghost" onClick={() => setShowForm(false)}>Закрыть</button>
              <button type="button" className="btn btn--primary" disabled={busy} onClick={() => void issue()}>
                {busy ? 'Сохраняем…' : 'Выпустить'}
              </button>
            </>
          )}
        >
          <label className="field">
            <span className="field__label">Сумма, BYN</span>
            <input className="input" type="number" min={1} max={5000} value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} />
          </label>
          <label className="field">
            <span className="field__label">Получатель</span>
            <input className="input" value={form.recipient_name} onChange={(event) => setForm({ ...form, recipient_name: event.target.value })} />
          </label>
          <label className="field">
            <span className="field__label">Телефон или email</span>
            <input className="input" value={form.recipient_phone || form.recipient_email} onChange={(event) => setForm({ ...form, recipient_phone: event.target.value, recipient_email: '' })} />
          </label>
        </Modal>
      )}
    </div>
  )
}
