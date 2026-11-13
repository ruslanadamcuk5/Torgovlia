import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api } from '../lib/api'
import { useApi } from '../lib/useApi'
import { useSite } from '../store/SettingsContext'
import { useToast } from '../store/ToastContext'
import { Icon } from '../components/icons'
import { Spinner } from '../components/ui'
import type { Appointment, BookingDay, BookingSlots } from '../lib/types'
import {
  formatMoney,
  humanDate,
  normalizePhoneInput,
  phonePretty,
  weekdayShort,
} from '../lib/format'

const STATUS_LABEL: Record<string, string> = {
  new: 'Новая',
  confirmed: 'Подтверждена',
  completed: 'Выполнена',
  cancelled: 'Отменена',
  no_show: 'Не пришёл',
}

const ACTIVE = ['new', 'confirmed']

function durationLabel(minutes: number): string {
  if (!minutes) return 'по договорённости'
  if (minutes < 60) return `${minutes} мин`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `${hours} ч ${rest} мин` : `${hours} ч`
}

function localDateTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const parts = new Intl.DateTimeFormat('ru-BY', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).formatToParts(date)
  const pick = (type: string) => parts.find((item) => item.type === type)?.value ?? ''
  return `${pick('day')}.${pick('month')}.${pick('year')} · ${pick('hour')}:${pick('minute')}`
}

interface LookupState {
  number?: string
  phone?: string
  action?: 'move' | 'cancel'
}

export default function AppointmentLookup() {
  const { site } = useSite()
  const { toast } = useToast()
  const location = useLocation()
  const preset = (location.state ?? {}) as LookupState

  const [number, setNumber] = useState(preset.number ?? '')
  const [phone, setPhone] = useState(preset.phone ? phonePretty(preset.phone) : '')
  const [appointment, setAppointment] = useState<Appointment | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const [moving, setMoving] = useState(false)
  const [moveDate, setMoveDate] = useState('')
  const [moveTime, setMoveTime] = useState('')

  const productId = appointment?.product_id ?? null
  const specialistId = appointment?.specialist_id ?? null

  const { data: days } = useApi<{ days: BookingDay[] }>(
    moving && productId
      ? `/booking/days?product_id=${productId}${specialistId ? `&specialist_id=${specialistId}` : ''}&days=21`
      : null,
    false,
  )

  const { data: slots, loading: slotsLoading } = useApi<BookingSlots>(
    moving && productId && moveDate
      ? `/booking/slots?product_id=${productId}&date=${moveDate}${specialistId ? `&specialist_id=${specialistId}` : ''}&exclude_appointment_id=${appointment?.id ?? ''}`
      : null,
    false,
  )

  const search = async (silent = false): Promise<Appointment | null> => {
    setError('')
    setAppointment(null)
    setMoving(false)
    if (!number.trim()) {
      if (!silent) setError('Введите номер записи')
      return null
    }
    if (phone.replace(/\D/g, '').length < 9) {
      if (!silent) setError('Введите телефон, указанный при записи')
      return null
    }
    setBusy(true)
    try {
      const result = await api<Appointment>('/booking/lookup', {
        method: 'POST',
        auth: false,
        body: { number: number.trim().toUpperCase(), phone },
      })
      setAppointment(result)
      return result
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Запись не найдена')
      return null
    } finally {
      setBusy(false)
    }
  }

  // Переход из экрана успешной записи: сразу ищем запись и, если просили,
  // открываем выбор нового времени.
  useEffect(() => {
    if (!preset.number || !preset.phone) return
    void search(true).then((found) => {
      if (found && preset.action === 'move') setMoving(true)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!days?.days.length) return
    if (moveDate && days.days.some((day) => day.date === moveDate)) return
    const firstOpen = days.days.find((day) => day.is_open && day.slots_available > 0)
    setMoveDate(firstOpen?.date ?? days.days[0].date)
  }, [days, moveDate])

  useEffect(() => {
    if (!slots) return
    const available = slots.slots.filter((slot) => slot.available)
    if (!available.some((slot) => slot.time === moveTime)) {
      setMoveTime(available[0]?.time ?? '')
    }
  }, [slots, moveTime])

  const canMove = useMemo(
    () => Boolean(appointment && ACTIVE.includes(appointment.status)),
    [appointment],
  )

  const cancel = async () => {
    if (!appointment) return
    if (!window.confirm(`Отменить запись ${appointment.number}?`)) return
    setBusy(true)
    try {
      const updated = await api<Appointment>('/booking/cancel', {
        method: 'POST',
        auth: false,
        body: {
          number: appointment.number,
          phone: appointment.phone,
          reason: 'Отменено клиентом на сайте',
        },
      })
      setAppointment(updated)
      setMoving(false)
      toast('Запись отменена', 'info')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось отменить запись', 'error')
    } finally {
      setBusy(false)
    }
  }

  const move = async () => {
    if (!appointment || !moveDate || !moveTime) return
    setBusy(true)
    try {
      const updated = await api<Appointment>('/booking/reschedule', {
        method: 'POST',
        auth: false,
        body: {
          number: appointment.number,
          phone: appointment.phone,
          starts_at: `${moveDate}T${moveTime}:00`,
          specialist_id: specialistId,
        },
      })
      setAppointment(updated)
      setMoving(false)
      toast('Запись перенесена — мы ждём вас в новое время', 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось перенести запись', 'error')
    } finally {
      setBusy(false)
    }
  }

  if (!site) return null

  return (
    <div className="container section">
      <div className="breadcrumbs">
        <Link to="/">Главная</Link>
        <Icon name="chevron-right" size={13} />
        <span>Моя запись</span>
      </div>
      <div className="page-head page-head--compact">
        <span className="eyebrow">Без регистрации</span>
        <h1>Моя запись</h1>
        <p className="page-head__sub">
          Введите номер записи и телефон — покажем время визита, дадим перенести
          или отменить его.
        </p>
      </div>

      <div className="lookup-grid">
        <div className="panel">
          <label className="field">
            <span className="field__label">Номер записи</span>
            <input
              className="input"
              value={number}
              onChange={(event) => setNumber(event.target.value.toUpperCase())}
              placeholder="Z261113-1234"
              autoCapitalize="characters"
            />
          </label>
          <label className="field">
            <span className="field__label">Телефон</span>
            <input
              className="input"
              value={phone}
              onChange={(event) => setPhone(normalizePhoneInput(event.target.value))}
              onBlur={() => setPhone((value) => phonePretty(value))}
              placeholder="+375 29 123-45-67"
              inputMode="tel"
            />
          </label>
          {error && (
            <div className="notice notice--error">
              <Icon name="alert" size={17} />
              <span>{error}</span>
            </div>
          )}
          <button
            type="button"
            className="btn btn--primary btn--lg btn--block"
            onClick={() => search()}
            disabled={busy}
          >
            {busy ? <Spinner size={18} /> : <Icon name="search" size={18} />} Найти запись
          </button>
          <p className="field__hint">
            Номер записи приходит в SMS сразу после записи. Если SMS не пришло —
            позвоните: {site.settings.phone}.
          </p>
        </div>

        <div className="panel panel--soft">
          <h3><Icon name="calendar" size={19} /> Что можно сделать</h3>
          <p>
            Перенести визит на другое свободное окно или отменить его. Изменения
            сразу попадают в расписание специалиста.
          </p>
          <div className="notice">
            <Icon name="clock" size={18} />
            <span>
              Свободные окна показываются сразу — выберите удобное время, и
              расписание специалиста обновится.
            </span>
          </div>
          <Link to="/booking" className="link-arrow">
            Записаться снова <Icon name="arrow-right" size={16} />
          </Link>
        </div>
      </div>

      {appointment && (
        <section className="lookup-result">
          <h2>Запись найдена</h2>
          <div className="booking-ticket">
            <div className="booking-ticket__head">
              <div>
                <span>Номер записи</span>
                <strong>{appointment.number}</strong>
              </div>
              <span
                className={`badge ${
                  appointment.status === 'confirmed'
                    ? 'badge--info'
                    : appointment.status === 'new'
                      ? 'badge--fresh'
                      : 'badge--muted'
                }`}
              >
                {STATUS_LABEL[appointment.status] ?? appointment.status}
              </span>
            </div>
            <dl className="booking-ticket__rows">
              <div><dt>Услуга</dt><dd>{appointment.service_title}</dd></div>
              {appointment.specialist_name && (
                <div><dt>Специалист</dt><dd>{appointment.specialist_name}</dd></div>
              )}
              <div><dt>Когда</dt><dd>{localDateTime(appointment.starts_at)}</dd></div>
              <div><dt>Длительность</dt><dd>{durationLabel(appointment.duration_minutes)}</dd></div>
              <div><dt>Стоимость</dt><dd>{formatMoney(appointment.price)}</dd></div>
              <div><dt>Клиент</dt><dd>{appointment.customer_name}</dd></div>
            </dl>
          </div>

          {canMove ? (
            <div className="booking-success__actions">
              <button
                type="button"
                className="btn btn--primary"
                onClick={() => setMoving((value) => !value)}
                disabled={busy}
              >
                <Icon name="calendar" size={17} /> {moving ? 'Скрыть время' : 'Перенести запись'}
              </button>
              <button type="button" className="btn btn--outline" onClick={cancel} disabled={busy}>
                {busy ? <Spinner size={17} /> : <Icon name="close" size={17} />}
                Отменить запись
              </button>
            </div>
          ) : (
            <p className="muted">
              {appointment.status === 'cancelled'
                ? 'Запись отменена. Можно выбрать новое время и записаться снова.'
                : 'Визит уже состоялся — изменения недоступны.'}
            </p>
          )}

          {moving && canMove && (
            <div className="panel">
              <h3><Icon name="calendar" size={18} /> Новое время</h3>
              <div className="booking-days">
                {days?.days.map((day) => (
                  <button
                    key={day.date}
                    type="button"
                    className={`booking-day ${day.date === moveDate ? 'is-active' : ''}`}
                    disabled={!day.is_open || day.slots_available === 0}
                    onClick={() => setMoveDate(day.date)}
                  >
                    <span>{weekdayShort(day.date)}</span>
                    <strong>{humanDate(day.date)}</strong>
                    <em>{day.slots_available > 0 ? `${day.slots_available} окон` : 'нет мест'}</em>
                  </button>
                ))}
              </div>
              {slotsLoading ? <Spinner size={20} /> : null}
              {slots && slots.is_open ? (
                <>
                  <div className="booking-slots">
                    {slots.slots.map((slot) => (
                      <button
                        key={slot.time}
                        type="button"
                        className={`booking-slot ${slot.time === moveTime ? 'is-active' : ''}`}
                        disabled={!slot.available}
                        onClick={() => setMoveTime(slot.time)}
                      >
                        {slot.time}
                      </button>
                    ))}
                  </div>
                  {slots.message && (
                    <div className="notice">
                      <Icon name="info" size={18} />
                      <span>{slots.message}</span>
                    </div>
                  )}
                </>
              ) : slots ? (
                <div className="notice">
                  <Icon name="info" size={18} />
                  <span>{slots.message || 'В этот день записи нет — выберите другую дату.'}</span>
                </div>
              ) : null}
              <button
                type="button"
                className="btn btn--primary btn--lg"
                disabled={busy || !moveDate || !moveTime}
                onClick={move}
              >
                {busy ? <Spinner size={18} /> : <Icon name="check" size={18} />}
                Перенести на {moveDate ? humanDate(moveDate) : '…'} {moveTime}
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
