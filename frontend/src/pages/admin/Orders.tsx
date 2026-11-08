import { useState } from 'react'
import { useApi } from '../../lib/useApi'
import { api, downloadFile } from '../../lib/api'
import { useToast } from '../../store/ToastContext'
import { useDebounced, Loader, Modal, Spinner, StatusBadge } from '../../components/ui'
import { Icon } from '../../components/icons'
import type { Order } from '../../lib/types'
import { formatMoney, formatQty, humanDate, statusLabel, unitShort } from '../../lib/format'

const STATUS_TABS = [
  { id: 'active', label: 'В работе' },
  { id: 'new', label: 'Новые' },
  { id: 'confirmed', label: 'Подтверждены' },
  { id: 'ready', label: 'Готовы' },
  { id: 'completed', label: 'Выданы' },
  { id: 'cancelled', label: 'Отменены' },
  { id: 'all', label: 'Все' },
]

const NEXT_ACTIONS: Record<string, { status: string; label: string; tone: string }[]> = {
  new: [
    { status: 'confirmed', label: 'Подтвердить', tone: 'primary' },
    { status: 'rejected', label: 'Отклонить', tone: 'danger' },
  ],
  confirmed: [
    { status: 'ready', label: 'Готова к выдаче', tone: 'primary' },
    { status: 'cancelled', label: 'Отменить', tone: 'danger' },
  ],
  ready: [
    { status: 'completed', label: 'Выдана', tone: 'primary' },
    { status: 'cancelled', label: 'Отменить', tone: 'danger' },
  ],
}

export default function AdminOrders() {
  const { toast } = useToast()
  const [status, setStatus] = useState('active')
  const [date, setDate] = useState('')
  const [query, setQuery] = useState('')
  const q = useDebounced(query)
  const [selected, setSelected] = useState<Order | null>(null)
  const [comment, setComment] = useState('')
  const [pickupDate, setPickupDate] = useState('')
  const [pickupTime, setPickupTime] = useState('')
  const [busy, setBusy] = useState(false)

  const params = new URLSearchParams({ limit: '100', status })
  if (date) params.set('pickup_date', date)
  if (q.trim()) params.set('q', q.trim())
  const { data, loading, reload } = useApi<{ items: Order[]; total: number }>(`/admin/orders?${params.toString()}`)

  const openOrder = (order: Order) => {
    setSelected(order)
    setComment(order.admin_comment)
    setPickupDate(order.pickup_date)
    setPickupTime(order.pickup_time)
  }

  const updateStatus = async (nextStatus: string, close = false) => {
    if (!selected) return
    setBusy(true)
    try {
      const updated = await api<Order>(`/admin/orders/${selected.id}`, {
        method: 'PATCH',
        body: {
          status: nextStatus,
          admin_comment: comment,
          pickup_date: pickupDate,
          pickup_time: pickupTime,
        },
      })
      toast(`Бронь ${updated.number}: ${statusLabel(updated.status).toLowerCase()}`)
      setSelected(updated)
      setComment(updated.admin_comment)
      reload()
      if (close) setSelected(null)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось обновить бронь', 'error')
    } finally {
      setBusy(false)
    }
  }

  const exportCsv = async () => {
    try {
      const params = new URLSearchParams()
      if (status !== 'all') params.set('status', status)
      await downloadFile(
        `/admin/orders/export.csv?${params.toString()}`,
        `orders-${new Date().toISOString().slice(0, 10)}.csv`,
      )
      toast('CSV-файл сохранён')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Ошибка экспорта', 'error')
    }
  }

  return (
    <div className="admin-page">
      <div className="admin-toolbar">
        <div className="admin-toolbar__left">
          <label className="search-field">
            <Icon name="search" size={17} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Номер, имя или телефон" type="search" />
          </label>
          <label className="field field--inline">
            <input className="input input--sm" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          </label>
          {date && <button type="button" className="btn btn--sm btn--ghost" onClick={() => setDate('')}>Сбросить дату</button>}
        </div>
        <div className="admin-toolbar__right">
          <span className="muted">{data ? `${data.total} броней` : '…'}</span>
          <button type="button" className="btn btn--sm btn--outline" onClick={exportCsv}><Icon name="download" size={16} /> CSV</button>
        </div>
      </div>

      <div className="admin-tabs">
        {STATUS_TABS.map((tab) => (
          <button key={tab.id} type="button" className={status === tab.id ? 'is-active' : ''} onClick={() => setStatus(tab.id)}>
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? <Loader /> : data && data.items.length > 0 ? (
        <div className="table-wrap">
          <table className="data-table data-table--orders">
            <thead>
              <tr>
                <th>Бронь</th>
                <th>Клиент</th>
                <th>Получение</th>
                <th>Состав</th>
                <th>Сумма</th>
                <th>Статус</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((order) => (
                <tr key={order.id} onClick={() => openOrder(order)} className="is-clickable">
                  <td>
                    <strong>{order.number}</strong>
                    <span className="table-sub">{new Date(order.created_at).toLocaleString('ru-BY', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</span>
                  </td>
                  <td>
                    <strong>{order.customer_name}</strong>
                    <span className="table-sub">{order.phone_formatted}</span>
                  </td>
                  <td>
                    <strong>{order.fulfillment === 'delivery' ? 'Доставка' : humanDate(order.pickup_date)}</strong>
                    <span className="table-sub">
                      {order.fulfillment === 'delivery'
                        ? `${humanDate(order.pickup_date)}, ${order.pickup_time}`
                        : order.pickup_time}
                    </span>
                  </td>
                  <td><span className="table-sub table-sub--clamp">{order.items.map((item) => item.title).join(', ')}</span></td>
                  <td><strong>{formatMoney(order.total_amount)}</strong></td>
                  <td><StatusBadge status={order.status} /></td>
                  <td><button type="button" className="icon-btn" onClick={(event) => { event.stopPropagation(); openOrder(order) }}><Icon name="chevron-right" size={18} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state">
          <span className="empty-state__icon"><Icon name="list" size={28} /></span>
          <h3>Броней нет</h3>
          <p>В выбранном фильтре заказов пока нет.</p>
        </div>
      )}

      {selected && (
        <Modal
          title={`Бронь ${selected.number}`}
          subtitle={`Создана ${new Date(selected.created_at).toLocaleString('ru-BY')} · источник: ${selected.source === 'app' ? 'приложение' : 'сайт'}`}
          onClose={() => setSelected(null)}
          size="lg"
          footer={(
            <>
              <button type="button" className="btn btn--ghost" onClick={() => setSelected(null)}>Закрыть</button>
              {NEXT_ACTIONS[selected.status]?.map((action) => (
                <button
                  key={action.status}
                  type="button"
                  className={`btn ${action.tone === 'primary' ? 'btn--primary' : 'btn--danger'}`}
                  disabled={busy}
                  onClick={() => updateStatus(action.status, action.status === 'completed' || action.status === 'rejected' || action.status === 'cancelled')}
                >
                  {busy ? <Spinner size={16} /> : action.label}
                </button>
              ))}
              <button type="button" className="btn btn--outline" disabled={busy} onClick={() => updateStatus(selected.status)}>
                Сохранить изменения
              </button>
            </>
          )}
        >
          <div className="order-detail">
            <div className="order-detail__top">
              <div className="order-detail__client">
                <span className="avatar">{selected.customer_name.slice(0, 1).toUpperCase()}</span>
                <div>
                  <strong>{selected.customer_name}</strong>
                  <a href={`tel:${selected.phone}`}><Icon name="phone" size={15} /> {selected.phone_formatted}</a>
                </div>
              </div>
              <StatusBadge status={selected.status} />
            </div>

            <div className="order-detail__pickup">
              <label className="field">
                <span className="field__label">{selected.fulfillment === 'delivery' ? 'Дата доставки' : 'Дата получения'}</span>
                <input className="input" type="date" value={pickupDate} onChange={(event) => setPickupDate(event.target.value)} />
              </label>
              <label className="field">
                <span className="field__label">Время</span>
                <input className="input" type="time" value={pickupTime} onChange={(event) => setPickupTime(event.target.value)} />
              </label>
              <div className="order-detail__sum">
                <span>Сумма</span>
                <strong>{formatMoney(selected.total_amount)}</strong>
              </div>
            </div>

            {selected.fulfillment === 'delivery' && (
              <div className="note-box note-box--delivery">
                <strong>
                  <Icon name="car" size={16} /> Доставка
                  {selected.delivery_zone_name ? ` · ${selected.delivery_zone_name}` : ''}
                </strong>
                <p>{selected.delivery_address}</p>
                {Boolean(selected.delivery_fee) && (
                  <span className="muted">Стоимость доставки: {formatMoney(selected.delivery_fee ?? 0)}</span>
                )}
              </div>
            )}

            <div className="order-detail__items">
              <h3>Состав заказа</h3>
              <table className="data-table data-table--compact">
                <thead><tr><th>Товар</th><th>Цена</th><th>Кол-во</th><th>Сумма</th></tr></thead>
                <tbody>
                  {selected.items.map((item) => (
                    <tr key={item.id}>
                      <td>{item.title}</td>
                      <td>{formatMoney(item.price)}</td>
                      <td>{formatQty(item.quantity)} {unitShort(item.unit)}</td>
                      <td><strong>{formatMoney(item.line_total)}</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {selected.comment && (
              <div className="note-box"><strong>Комментарий покупателя</strong><p>{selected.comment}</p></div>
            )}

            <label className="field">
              <span className="field__label">Комментарий продавца (виден покупателю)</span>
              <textarea className="textarea" rows={2} value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Например: разделали на порции" />
            </label>

            <div className="order-history">
              <h3>История статусов</h3>
              <ul>
                {selected.status_history.map((entry, index) => (
                  <li key={index}>
                    <span className="dot" />
                    <div>
                      <strong>{statusLabel(entry.status)}</strong>
                      <span>{new Date(entry.at).toLocaleString('ru-BY')} · {entry.by}</span>
                      {entry.comment && <p>{entry.comment}</p>}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
