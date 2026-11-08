import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Loader, Spinner } from '../../components/ui'
import { Icon } from '../../components/icons'
import { formatMoney } from '../../lib/format'

interface LevelInfo {
  code: string
  title: string
  multiplier: number
  threshold: number
  next: { title: string; threshold: number; remaining: number } | null
}

interface Customer {
  key: string
  user_id: number | null
  name: string
  phone: string
  phone_raw: string
  email: string
  consent: boolean
  registered: boolean
  orders: number
  spent: number
  avg_check: number
  first_order: string | null
  last_order: string | null
  registered_at: string | null
  tags: string[]
  notes_count: number
  segments: string[]
  loyalty: { balance: number; level: string; level_info: LevelInfo } | null
}

interface Segment {
  code: string
  title: string
  description: string
  count: number
}

interface ListData {
  items: Customer[]
  total: number
  summary: {
    customers: number
    consent: number
    revenue: number
    avg_check: number
    segments: Record<string, number>
  }
  segments: Segment[]
}

interface CrmNote {
  id: number
  body: string
  author: string
  created_at: string
}

interface Detail extends Customer {
  order_list: {
    id: number
    number: string
    status: string
    total_amount: number
    items_count: number
    pickup_date: string
    created_at: string
  }[]
  notes: CrmNote[]
  all_orders: number
}

const ORDER_STATUS: Record<string, string> = {
  new: 'Новая',
  confirmed: 'Подтверждена',
  ready: 'Готова',
  completed: 'Получена',
  cancelled: 'Отменена',
  rejected: 'Отклонена',
}

const SEGMENT_SHORT: Record<string, string> = {
  with_orders: 'С покупками',
  no_orders: 'Без покупок',
  recent: 'Активный',
  inactive: 'Спящий',
  vip: 'VIP',
  new: 'Новый',
}

export default function Crm() {
  const { toast } = useToast()
  const { data: features, loading: featuresLoading } = useApi<{ services: Record<string, boolean> }>(
    '/admin/services/features',
  )
  const enabled = Boolean(features?.services.crm)

  const [search, setSearch] = useState('')
  const [segment, setSegment] = useState('all')
  const { data, loading, reload } = useApi<ListData>(
    enabled ? `/admin/crm?segment=${segment}&limit=400` : null,
  )

  const [selected, setSelected] = useState<string | null>(null)
  const [card, setCard] = useState<Detail | null>(null)
  const [cardLoading, setCardLoading] = useState(false)
  const [tag, setTag] = useState('')
  const [note, setNote] = useState('')
  const [savingNote, setSavingNote] = useState(false)

  const items = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return data?.items ?? []
    return (data?.items ?? []).filter((item) =>
      `${item.name} ${item.phone} ${item.phone_raw} ${item.email}`.toLowerCase().includes(query),
    )
  }, [data, search])

  const loadCard = async (key: string) => {
    setCardLoading(true)
    try {
      const result = await api<Detail>(`/admin/crm/customers/${encodeURIComponent(key)}`)
      setCard(result)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось открыть карточку', 'error')
      setSelected(null)
    } finally {
      setCardLoading(false)
    }
  }

  useEffect(() => {
    if (selected) void loadCard(selected)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected])

  const openCustomer = (customer: Customer) => {
    setSelected(customer.key)
    setCard(null)
    setTag('')
    setNote('')
  }

  const addTag = async () => {
    if (!card || !tag.trim()) return
    try {
      await api(`/admin/crm/customers/${encodeURIComponent(card.key)}/tags`, {
        method: 'POST',
        body: { tag: tag.trim() },
      })
      setTag('')
      void loadCard(card.key)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось добавить метку', 'error')
    }
  }

  const removeTag = async (value: string) => {
    if (!card) return
    try {
      await api(
        `/admin/crm/customers/${encodeURIComponent(card.key)}/tags?tag=${encodeURIComponent(value)}`,
        { method: 'DELETE' },
      )
      void loadCard(card.key)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось удалить метку', 'error')
    }
  }

  const addNote = async () => {
    if (!card || !note.trim()) return
    setSavingNote(true)
    try {
      await api(`/admin/crm/customers/${encodeURIComponent(card.key)}/notes`, {
        method: 'POST',
        body: { body: note.trim() },
      })
      setNote('')
      void loadCard(card.key)
      reload()
      toast('Заметка добавлена')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось добавить заметку', 'error')
    } finally {
      setSavingNote(false)
    }
  }

  const removeNote = async (id: number) => {
    if (!card || !window.confirm('Удалить заметку?')) return
    try {
      await api(`/admin/crm/notes/${id}`, { method: 'DELETE' })
      void loadCard(card.key)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось удалить заметку', 'error')
    }
  }

  if (featuresLoading) return <Loader />

  if (!enabled) {
    return (
      <div className="admin-page">
        <section className="panel panel--accent">
          <div className="panel__head"><h2>Клиенты</h2></div>
          <p>
            CRM с карточкой клиента, заметками и метками доступна на тарифе <strong>«Про»</strong>.
            Здесь собирается вся база покупателей: заказы, контакты и сегменты.
          </p>
          <Link to="/admin/services" className="btn btn--primary">
            Перейти к сервисам <Icon name="arrow-right" size={17} />
          </Link>
        </section>
      </div>
    )
  }

  return (
    <div className="admin-page crm-page">
      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Клиенты</h2>
            <p className="muted">
              Зарегистрированные покупатели и гости с заказами. Сегменты считаются по
              покупкам и согласию на обработку данных.
            </p>
          </div>
          <div className="crm-search">
            <Icon name="search" size={16} />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Имя, телефон или почта"
              maxLength={120}
            />
          </div>
        </div>

        <div className="crm-stats">
          <div><span>Клиентов</span><strong>{data?.summary.customers ?? 0}</strong></div>
          <div><span>С покупками</span><strong>{data?.summary.segments.with_orders ?? 0}</strong></div>
          <div><span>Без покупок</span><strong>{data?.summary.segments.no_orders ?? 0}</strong></div>
          <div><span>VIP</span><strong>{data?.summary.segments.vip ?? 0}</strong></div>
          <div><span>Выручка</span><strong>{formatMoney(data?.summary.revenue ?? 0)}</strong></div>
          <div><span>Средний чек</span><strong>{formatMoney(data?.summary.avg_check ?? 0)}</strong></div>
        </div>

        <div className="crm-tabs">
          {(data?.segments ?? [{ code: 'all', title: 'Все клиенты', description: '', count: 0 }]).map((item) => (
            <button
              key={item.code}
              type="button"
              className={segment === item.code ? 'is-active' : ''}
              onClick={() => setSegment(item.code)}
              title={item.description}
            >
              {item.code === 'all' ? 'Все' : item.title}
              <span>{item.count}</span>
            </button>
          ))}
        </div>

        {loading && <p className="muted">Загружаем клиентов…</p>}

        <div className="crm-list">
          {items.map((customer) => (
            <button
              type="button"
              className="crm-row"
              key={customer.key}
              onClick={() => openCustomer(customer)}
            >
              <span className="crm-avatar">{customer.name.slice(0, 1).toUpperCase()}</span>
              <span className="crm-row__main">
                <span className="crm-row__name">
                  {customer.name}
                  {!customer.consent && <em className="crm-flag crm-flag--warn">без согласия</em>}
                  {customer.loyalty && (
                    <em className={`loyalty-badge loyalty-badge--${customer.loyalty.level}`}>
                      {customer.loyalty.level_info.title}
                    </em>
                  )}
                </span>
                <small>
                  {customer.phone || 'без телефона'}
                  {customer.email ? ` · ${customer.email}` : ''}
                </small>
                <span className="crm-row__tags">
                  {customer.tags.map((value) => (
                    <em key={value} className="crm-tag">{value}</em>
                  ))}
                  {customer.segments
                    .filter((code) => code !== 'all')
                    .slice(0, 3)
                    .map((code) => (
                      <em key={code} className="crm-segment">{SEGMENT_SHORT[code] ?? code}</em>
                    ))}
                </span>
              </span>
              <span className="crm-row__stats">
                <span>{customer.orders} заказ(ов)</span>
                <strong>{formatMoney(customer.spent)}</strong>
              </span>
              <span className="crm-row__last">
                <span>{customer.last_order ? new Date(customer.last_order).toLocaleDateString('ru-BY') : '—'}</span>
                <small>
                  {customer.notes_count > 0 ? `${customer.notes_count} заметок` : 'нет заметок'}
                </small>
              </span>
              <Icon name="chevron-right" size={16} />
            </button>
          ))}
          {!loading && items.length === 0 && (
            <div className="crm-empty">
              <Icon name="users" size={22} />
              <p>{search ? 'По запросу никого не нашли.' : 'В этом сегменте пока нет клиентов.'}</p>
            </div>
          )}
        </div>
      </section>

      {selected && (
        <div className="crm-modal" role="dialog" aria-modal="true">
          <div className="crm-modal__card">
            <div className="crm-modal__head">
              <div>
                <h3>{card?.name ?? 'Карточка клиента'}</h3>
                {card && (
                  <p className="muted">
                    {card.phone || 'без телефона'}
                    {card.email ? ` · ${card.email}` : ''}
                  </p>
                )}
              </div>
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => setSelected(null)}>
                <Icon name="close" size={16} />
              </button>
            </div>

            {cardLoading && <div className="crm-modal__loading"><Spinner size={18} /> Загружаем карточку…</div>}

            {card && (
              <div className="crm-modal__body">
                <div className="crm-flags">
                  <span className={card.consent ? 'crm-flag' : 'crm-flag crm-flag--warn'}>
                    {card.consent ? 'Согласие на обработку есть' : 'Нет согласия на обработку'}
                  </span>
                  <span className="crm-flag">{card.registered ? 'Зарегистрирован' : 'Гость'}</span>
                  {card.loyalty && (
                    <span className={`loyalty-badge loyalty-badge--${card.loyalty.level}`}>
                      {card.loyalty.level_info.title} · {card.loyalty.balance} баллов
                    </span>
                  )}
                </div>

                <div className="crm-card-stats">
                  <div><span>Заказов</span><strong>{card.orders}</strong></div>
                  <div><span>Потратил</span><strong>{formatMoney(card.spent)}</strong></div>
                  <div><span>Средний чек</span><strong>{formatMoney(card.avg_check)}</strong></div>
                  <div><span>Последний заказ</span><strong>{card.last_order ? new Date(card.last_order).toLocaleDateString('ru-BY') : '—'}</strong></div>
                </div>

                <section className="crm-block">
                  <h4>Метки</h4>
                  <div className="crm-tag-list">
                    {card.tags.map((value) => (
                      <span className="crm-tag crm-tag--removable" key={value}>
                        {value}
                        <button type="button" onClick={() => removeTag(value)} aria-label={`Удалить метку ${value}`}>
                          <Icon name="close" size={12} />
                        </button>
                      </span>
                    ))}
                    {card.tags.length === 0 && <span className="muted">Меток пока нет</span>}
                  </div>
                  <div className="crm-inline-form">
                    <input
                      className="input input--sm"
                      value={tag}
                      onChange={(event) => setTag(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          event.preventDefault()
                          void addTag()
                        }
                      }}
                      maxLength={40}
                      placeholder="Постоянный, опт, доставка…"
                    />
                    <button type="button" className="btn btn--outline btn--sm" onClick={addTag} disabled={!tag.trim()}>
                      <Icon name="plus" size={15} /> Добавить
                    </button>
                  </div>
                </section>

                <section className="crm-block">
                  <h4>Заметки</h4>
                  <div className="crm-notes">
                    {card.notes.map((row) => (
                      <div className="crm-note" key={row.id}>
                        <p>{row.body}</p>
                        <small>
                          {row.author || 'Менеджер'} · {new Date(row.created_at).toLocaleString('ru-BY')}
                        </small>
                        <button type="button" className="btn btn--ghost btn--sm" onClick={() => removeNote(row.id)}>
                          <Icon name="trash" size={14} />
                        </button>
                      </div>
                    ))}
                    {card.notes.length === 0 && <p className="muted">Заметок пока нет.</p>}
                  </div>
                  <div className="crm-note-form">
                    <textarea
                      className="textarea"
                      rows={3}
                      value={note}
                      onChange={(event) => setNote(event.target.value)}
                      maxLength={2000}
                      placeholder="Что важно помнить об этом клиенте"
                    />
                    <button type="button" className="btn btn--primary btn--sm" onClick={addNote} disabled={savingNote || !note.trim()}>
                      {savingNote ? <Spinner size={15} /> : <Icon name="plus" size={15} />} Добавить заметку
                    </button>
                  </div>
                </section>

                <section className="crm-block">
                  <h4>Заказы</h4>
                  <div className="crm-orders">
                    {card.order_list.map((order) => (
                      <div className="crm-order" key={order.id}>
                        <strong>{order.number}</strong>
                        <span className={`crm-order__status crm-order__status--${order.status}`}>
                          {ORDER_STATUS[order.status] ?? order.status}
                        </span>
                        <span className="muted">{new Date(order.created_at).toLocaleDateString('ru-BY')}</span>
                        <span className="muted">{order.items_count} поз.</span>
                        <b>{formatMoney(order.total_amount)}</b>
                      </div>
                    ))}
                    {card.order_list.length === 0 && <p className="muted">Заказов ещё не было.</p>}
                  </div>
                </section>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
