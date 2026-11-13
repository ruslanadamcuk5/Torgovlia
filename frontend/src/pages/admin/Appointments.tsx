import { useMemo, useState } from 'react'
import { useApi } from '../../lib/useApi'
import { api } from '../../lib/api'
import { useToast } from '../../store/ToastContext'
import { useDebounced, Loader, Modal, Spinner } from '../../components/ui'
import { Icon } from '../../components/icons'
import type {
  Appointment,
  AppointmentStatus,
  BookingSlots,
  Product,
  Specialist,
} from '../../lib/types'
import {
  formatMoney,
  normalizePhoneInput,
  phonePretty,
} from '../../lib/format'

const STATUS_TABS = [
  { id: 'active', label: 'Активные' },
  { id: 'new', label: 'Новые' },
  { id: 'confirmed', label: 'Подтверждены' },
  { id: 'completed', label: 'Выполнены' },
  { id: 'cancelled', label: 'Отменены' },
  { id: 'no_show', label: 'Не пришли' },
  { id: 'all', label: 'Все' },
]

const STATUS_LABEL: Record<string, string> = {
  new: 'Новая',
  confirmed: 'Подтверждена',
  completed: 'Выполнена',
  cancelled: 'Отменена',
  no_show: 'Не пришёл',
}

const STATUS_TONE: Record<string, string> = {
  new: 'gold',
  confirmed: 'info',
  completed: 'fresh',
  cancelled: 'muted',
  no_show: 'danger',
}

const NEXT_ACTIONS: Record<string, { status: AppointmentStatus; label: string; tone: string }[]> = {
  new: [
    { status: 'confirmed', label: 'Подтвердить', tone: 'primary' },
    { status: 'no_show', label: 'Не пришёл', tone: 'ghost' },
    { status: 'cancelled', label: 'Отменить', tone: 'danger' },
  ],
  confirmed: [
    { status: 'completed', label: 'Выполнена', tone: 'primary' },
    { status: 'no_show', label: 'Не пришёл', tone: 'ghost' },
    { status: 'cancelled', label: 'Отменить', tone: 'danger' },
  ],
}

function localTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('ru-BY', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function fullLocal(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('ru-BY', {
    day: '2-digit',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

const MANUAL_EMPTY = {
  productId: '',
  specialistId: '',
  date: '',
  time: '',
  name: '',
  phone: '',
  comment: '',
}

export default function AdminAppointments() {
  const { toast } = useToast()
  const [status, setStatus] = useState('active')
  const [date, setDate] = useState('')
  const [query, setQuery] = useState('')
  const q = useDebounced(query)
  const [selected, setSelected] = useState<Appointment | null>(null)
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)

  const [manualOpen, setManualOpen] = useState(false)
  const [manual, setManual] = useState(MANUAL_EMPTY)
  const [manualSaving, setManualSaving] = useState(false)

  const params = new URLSearchParams({ limit: '200', status })
  if (date) {
    params.set('date_from', date)
    params.set('date_to', date)
  }
  if (q.trim()) params.set('q', q.trim())
  const { data, loading, reload } = useApi<{ items: Appointment[]; total: number }>(
    `/admin/appointments?${params.toString()}`,
  )

  const { data: services } = useApi<{ items: Product[] }>(
    manualOpen ? '/services?limit=100' : null,
    false,
  )
  const { data: specialists } = useApi<{ items: Specialist[] }>(
    manualOpen && manual.productId
      ? `/specialists?service_id=${manual.productId}`
      : '/specialists',
    false,
  )
  const { data: slots } = useApi<BookingSlots>(
    manualOpen && manual.productId && manual.date
      ? `/booking/slots?product_id=${manual.productId}&date=${manual.date}${manual.specialistId ? `&specialist_id=${manual.specialistId}` : ''}`
      : null,
    false,
  )

  const today = useMemo(() => new Date().toISOString().slice(0, 10), [])
  const manualService = services?.items.find((item) => String(item.id) === manual.productId) ?? null

  const openAppointment = (item: Appointment) => {
    setSelected(item)
    setComment('')
  }

  const updateStatus = async (nextStatus: AppointmentStatus, close = false) => {
    if (!selected) return
    setBusy(true)
    try {
      const updated = await api<Appointment>(`/admin/appointments/${selected.id}`, {
        method: 'PATCH',
        body: { status: nextStatus, admin_comment: comment },
      })
      toast(`Запись ${updated.number}: ${(STATUS_LABEL[updated.status] ?? updated.status).toLowerCase()}`)
      setSelected(updated)
      setComment('')
      reload()
      if (close) setSelected(null)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось обновить запись', 'error')
    } finally {
      setBusy(false)
    }
  }

  const sendReminder = async () => {
    if (!selected) return
    setBusy(true)
    try {
      const result = await api<{ channel: string; appointment: Appointment }>(
        `/admin/appointments/${selected.id}/remind`,
        { method: 'POST' },
      )
      toast(result.channel === 'email' ? 'Напоминание отправлено письмом' : 'Напоминание отправлено в SMS')
      setSelected(result.appointment)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось отправить напоминание', 'error')
    } finally {
      setBusy(false)
    }
  }

  const createManual = async () => {
    if (!manual.productId || !manual.date || !manual.time) {
      toast('Выберите услугу, дату и время', 'error')
      return
    }
    if (manual.name.trim().length < 2 || manual.phone.replace(/\D/g, '').length < 9) {
      toast('Укажите имя и телефон клиента', 'error')
      return
    }
    setManualSaving(true)
    try {
      const created = await api<Appointment>('/admin/appointments', {
        method: 'POST',
        body: {
          product_id: Number(manual.productId),
          specialist_id: manual.specialistId ? Number(manual.specialistId) : null,
          starts_at: `${manual.date}T${manual.time}:00`,
          customer_name: manual.name.trim(),
          phone: normalizePhoneInput(manual.phone),
          comment: manual.comment.trim(),
          consent_personal_data: true,
          status: 'confirmed',
        },
      })
      toast(`Клиент записан: ${created.number}`)
      setManual(MANUAL_EMPTY)
      setManualOpen(false)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось создать запись', 'error')
    } finally {
      setManualSaving(false)
    }
  }

  return (
    <div className="admin-page">
      <div className="admin-toolbar">
        <div className="admin-toolbar__left">
          <label className="search-field">
            <Icon name="search" size={17} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Номер, имя, телефон или услуга"
              type="search"
            />
          </label>
          <label className="field field--inline">
            <input
              className="input input--sm"
              type="date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
          </label>
          {date && (
            <button type="button" className="btn btn--sm btn--ghost" onClick={() => setDate('')}>
              Сбросить дату
            </button>
          )}
        </div>
        <div className="admin-toolbar__right">
          <span className="muted">{data ? `${data.total} записей` : '…'}</span>
          <button type="button" className="btn btn--sm btn--primary" onClick={() => setManualOpen(true)}>
            <Icon name="plus" size={16} /> Записать клиента
          </button>
        </div>
      </div>

      <div className="admin-tabs">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={status === tab.id ? 'is-active' : ''}
            onClick={() => setStatus(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? <Loader /> : data && data.items.length > 0 ? (
        <div className="table-wrap">
          <table className="data-table data-table--orders">
            <thead>
              <tr>
                <th>Когда</th>
                <th>Клиент</th>
                <th>Услуга</th>
                <th>Специалист</th>
                <th>Стоимость</th>
                <th>Статус</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr key={item.id} onClick={() => openAppointment(item)} className="is-clickable">
                  <td>
                    <strong>{localTime(item.starts_at)}</strong>
                    <span className="table-sub">{item.duration_minutes} мин</span>
                  </td>
                  <td>
                    <strong>{item.customer_name}</strong>
                    <span className="table-sub">{item.phone_formatted}</span>
                  </td>
                  <td>
                    <strong>{item.service_title}</strong>
                    <span className="table-sub">{item.number}</span>
                  </td>
                  <td><span className="table-sub">{item.specialist_name || 'любой'}</span></td>
                  <td><strong>{formatMoney(item.price)}</strong></td>
                  <td><span className={`badge badge--${STATUS_TONE[item.status] ?? 'muted'}`}>{STATUS_LABEL[item.status] ?? item.status}</span></td>
                  <td>
                    <button
                      type="button"
                      className="icon-btn"
                      onClick={(event) => { event.stopPropagation(); openAppointment(item) }}
                    >
                      <Icon name="chevron-right" size={18} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state">
          <span className="empty-state__icon"><Icon name="calendar" size={28} /></span>
          <h3>Записей нет</h3>
          <p>В выбранном фильтре записей пока нет. Клиента можно записать вручную.</p>
          <button type="button" className="btn btn--primary" onClick={() => setManualOpen(true)}>
            <Icon name="plus" size={16} /> Записать клиента
          </button>
        </div>
      )}

      {selected && (
        <Modal
          title={`Запись ${selected.number}`}
          subtitle={`${fullLocal(selected.starts_at)} · ${selected.duration_minutes} мин · источник: ${
            selected.source === 'admin' ? 'админка' : selected.source === 'app' ? 'приложение' : 'сайт'
          }`}
          onClose={() => setSelected(null)}
          size="lg"
          footer={(
            <>
              <button type="button" className="btn btn--ghost" onClick={() => setSelected(null)}>Закрыть</button>
              {['new', 'confirmed'].includes(selected.status) && (
                <button
                  type="button"
                  className="btn btn--outline"
                  disabled={busy}
                  onClick={sendReminder}
                >
                  {busy ? <Spinner size={16} /> : selected.reminder_sent_at ? 'Напомнить снова' : 'Напомнить клиенту'}
                </button>
              )}
              {(NEXT_ACTIONS[selected.status] ?? []).map((action) => (
                <button
                  key={action.status}
                  type="button"
                  className={`btn ${action.tone === 'primary' ? 'btn--primary' : action.tone === 'danger' ? 'btn--danger' : 'btn--outline'}`}
                  disabled={busy}
                  onClick={() => updateStatus(action.status, ['cancelled', 'no_show'].includes(action.status))}
                >
                  {busy ? <Spinner size={16} /> : action.label}
                </button>
              ))}
              <button
                type="button"
                className="btn btn--outline"
                disabled={busy || !comment.trim()}
                onClick={() => updateStatus(selected.status)}
              >
                Сохранить комментарий
              </button>
            </>
          )}
        >
          <div className="appointment-detail">
            <div className="appointment-detail__top">
              <div className="order-detail__client">
                <span className="avatar">{selected.customer_name.slice(0, 1).toUpperCase()}</span>
                <div>
                  <strong>{selected.customer_name}</strong>
                  <a href={`tel:${selected.phone}`}><Icon name="phone" size={15} /> {selected.phone_formatted}</a>
                  {selected.email && <span className="table-sub">{selected.email}</span>}
                </div>
              </div>
              <span className={`badge badge--${STATUS_TONE[selected.status] ?? 'muted'}`}>
                {STATUS_LABEL[selected.status] ?? selected.status}
              </span>
            </div>

            <div className="appointment-detail__facts">
              <div>
                <span><Icon name="sparkles" size={16} /> Услуга</span>
                <strong>{selected.service_title}</strong>
              </div>
              <div>
                <span><Icon name="user" size={16} /> Специалист</span>
                <strong>{selected.specialist_name || 'любой свободный'}</strong>
              </div>
              <div>
                <span><Icon name="clock" size={16} /> Время</span>
                <strong>{fullLocal(selected.starts_at)}</strong>
              </div>
              <div>
                <span><Icon name="wallet" size={16} /> Стоимость</span>
                <strong>{formatMoney(selected.price)}</strong>
              </div>
              <div>
                <span><Icon name="send" size={16} /> Напоминание</span>
                <strong>
                  {selected.reminder_sent_at
                    ? `отправлено ${new Date(selected.reminder_sent_at).toLocaleString('ru-BY')}`
                    : 'ещё не отправлено'}
                </strong>
              </div>
            </div>

            {selected.comment && (
              <div className="note-box">
                <strong>Комментарий клиента</strong>
                <p>{selected.comment}</p>
              </div>
            )}

            {selected.admin_comment && (
              <div className="note-box">
                <strong>Заметки администратора</strong>
                <p>{selected.admin_comment}</p>
              </div>
            )}

            <label className="field">
              <span className="field__label">Комментарий к смене статуса</span>
              <textarea
                className="textarea"
                rows={2}
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                placeholder="Например: клиент позвонил и перенёс визит"
              />
            </label>

            <div className="order-history">
              <h3>История записи</h3>
              <ul>
                {(selected.status_history ?? []).map((entry, index) => (
                  <li key={index}>
                    <span className="dot" />
                    <div>
                      <strong>{STATUS_LABEL[entry.status] ?? entry.status}</strong>
                      <span>{new Date(entry.at).toLocaleString('ru-BY')} · {entry.actor || 'система'}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Modal>
      )}

      {manualOpen && (
        <Modal
          title="Записать клиента"
          subtitle="Ручная запись: клиент пришёл или позвонил"
          onClose={() => setManualOpen(false)}
          size="lg"
          footer={(
            <>
              <button type="button" className="btn btn--ghost" onClick={() => setManualOpen(false)}>Отмена</button>
              <button type="button" className="btn btn--primary" disabled={manualSaving} onClick={createManual}>
                {manualSaving ? <Spinner size={16} /> : <Icon name="check" size={16} />}
                Записать
              </button>
            </>
          )}
        >
          <div className="booking-form">
            <div className="booking-form__grid">
              <label className="field">
                <span className="field__label">Услуга *</span>
                <select
                  className="input"
                  value={manual.productId}
                  onChange={(event) => setManual({
                    ...manual,
                    productId: event.target.value,
                    specialistId: '',
                    time: '',
                  })}
                >
                  <option value="">Выберите услугу</option>
                  {services?.items.map((item) => (
                    <option key={item.id} value={item.id}>{item.title}</option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span className="field__label">Специалист</span>
                <select
                  className="input"
                  value={manual.specialistId}
                  onChange={(event) => setManual({ ...manual, specialistId: event.target.value, time: '' })}
                >
                  <option value="">Любой свободный</option>
                  {specialists?.items.map((person) => (
                    <option key={person.id} value={person.id}>{person.name}</option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span className="field__label">Дата *</span>
                <input
                  className="input"
                  type="date"
                  min={today}
                  value={manual.date}
                  onChange={(event) => setManual({ ...manual, date: event.target.value, time: '' })}
                />
              </label>

              <label className="field">
                <span className="field__label">Имя клиента *</span>
                <input
                  className="input"
                  value={manual.name}
                  onChange={(event) => setManual({ ...manual, name: event.target.value })}
                  placeholder="Имя"
                />
              </label>

              <label className="field">
                <span className="field__label">Телефон *</span>
                <input
                  className="input"
                  value={manual.phone}
                  onChange={(event) => setManual({ ...manual, phone: phonePretty(event.target.value) })}
                  placeholder="+375 (29) 000-00-00"
                  inputMode="tel"
                />
              </label>

              <label className="field booking-form__full">
                <span className="field__label">Комментарий</span>
                <input
                  className="input"
                  value={manual.comment}
                  onChange={(event) => setManual({ ...manual, comment: event.target.value })}
                  placeholder="Пожелания клиента"
                />
              </label>
            </div>

            {manual.productId && manual.date && (
              <div className="manual-slots">
                <span className="field__label">Свободное время</span>
                {slots?.is_open ? (
                  <div className="booking-slots">
                    {slots.slots.map((slot) => (
                      <button
                        key={slot.time}
                        type="button"
                        className={`booking-slot ${slot.time === manual.time ? 'is-active' : ''}`}
                        disabled={!slot.available}
                        onClick={() => setManual({ ...manual, time: slot.time })}
                      >
                        {slot.time}
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="notice">
                    <Icon name="info" size={18} />
                    <span>{slots?.message || 'В этот день записи нет.'}</span>
                  </div>
                )}
                {manualService && (
                  <span className="muted">
                    {manualService.title} · {manualService.duration_minutes} мин · {formatMoney(manualService.final_price)}
                  </span>
                )}
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  )
}
