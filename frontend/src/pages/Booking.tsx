import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useSite } from '../store/SettingsContext'
import { useAuth } from '../store/AuthContext'
import { useToast } from '../store/ToastContext'
import { useApi } from '../lib/useApi'
import { api, assetUrl } from '../lib/api'
import { Icon } from '../components/icons'
import { EmptyState, Loader, Spinner } from '../components/ui'
import type {
  Appointment,
  BookingDay,
  BookingSlots,
  Product,
  Specialist,
} from '../lib/types'
import {
  addDaysIso,
  formatMoney,
  humanDate,
  normalizePhoneInput,
  phonePretty,
  weekdayShort,
} from '../lib/format'

function durationLabel(minutes: number): string {
  if (!minutes) return 'по договорённости'
  if (minutes < 60) return `${minutes} мин`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `${hours} ч ${rest} мин` : `${hours} ч`
}

function localDateInput(value: string): string {
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

const STEPS = [
  { id: 1, label: 'Услуга' },
  { id: 2, label: 'Специалист' },
  { id: 3, label: 'Время' },
  { id: 4, label: 'Контакты' },
]

const CONTACT_EMPTY = {
  name: '',
  phone: '',
  email: '',
  comment: '',
  consent: false,
}

export default function Booking() {
  const { site } = useSite()
  const { user } = useAuth()
  const { toast } = useToast()
  const [params] = useSearchParams()

  const presetSlug = params.get('service') ?? ''
  const presetSpecialist = Number(params.get('specialist') ?? '') || null

  const { data: services, loading: servicesLoading } = useApi<{ items: Product[] }>(
    '/services?limit=100&sort=default',
    false,
  )
  const { data: presetService } = useApi<Product>(
    presetSlug ? `/products/${presetSlug}` : null,
    false,
  )

  const [step, setStep] = useState(1)
  const [serviceId, setServiceId] = useState<number | null>(null)
  const [specialistId, setSpecialistId] = useState<number | null>(presetSpecialist)
  const [date, setDate] = useState('')
  const [time, setTime] = useState('')
  const [contact, setContact] = useState(CONTACT_EMPTY)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [created, setCreated] = useState<Appointment | null>(null)
  const [cancelled, setCancelled] = useState(false)

  const selected = useMemo<Product | null>(() => {
    if (presetService && presetService.id === serviceId) return presetService
    return services?.items.find((item) => item.id === serviceId) ?? null
  }, [presetService, services, serviceId])

  // Предвыбор услуги из карточки или меню.
  useEffect(() => {
    if (!serviceId && presetService && presetService.kind === 'service') {
      setServiceId(presetService.id)
    }
  }, [presetService, serviceId])

  useEffect(() => {
    if (serviceId || !services?.items.length || presetSlug) return
    setServiceId(services.items[0].id)
  }, [services, serviceId, presetSlug])

  const { data: specialists, loading: specialistsLoading } = useApi<{ items: Specialist[] }>(
    serviceId ? `/specialists?service_id=${serviceId}` : null,
    false,
  )

  const { data: days } = useApi<{ days: BookingDay[] }>(
    serviceId
      ? `/booking/days?product_id=${serviceId}${specialistId ? `&specialist_id=${specialistId}` : ''}&days=21`
      : null,
    false,
  )

  const { data: slots, loading: slotsLoading } = useApi<BookingSlots>(
    serviceId && date
      ? `/booking/slots?product_id=${serviceId}&date=${date}${specialistId ? `&specialist_id=${specialistId}` : ''}`
      : null,
    false,
  )

  useEffect(() => {
    if (!user) return
    setContact((current) => ({
      ...current,
      name: current.name || user.full_name,
      phone: current.phone || user.phone,
      email: current.email || (user.email ?? ''),
    }))
  }, [user])

  useEffect(() => {
    if (!days?.days.length) return
    if (date && days.days.some((day) => day.date === date)) return
    const firstOpen = days.days.find((day) => day.is_open && day.slots_available > 0)
    setDate(firstOpen?.date ?? days.days[0].date)
  }, [days, date])

  useEffect(() => {
    if (!slots) return
    const available = slots.slots.filter((slot) => slot.available)
    if (!available.some((slot) => slot.time === time)) {
      setTime(available[0]?.time ?? '')
    }
  }, [slots, time])

  // Смена услуги сбрасывает выбранное время: слоты могли быть другими.
  const chooseService = (id: number) => {
    setServiceId(id)
    setSpecialistId(null)
    setDate('')
    setTime('')
    setStep(2)
  }

  const chooseSpecialist = (id: number | null) => {
    setSpecialistId(id)
    setDate('')
    setTime('')
    setStep(3)
  }

  const submit = async () => {
    if (!selected || !time || !date) return
    setError('')
    if (contact.name.trim().length < 2) {
      setError('Укажите имя — так администратор будет знать, кого ждать.')
      return
    }
    const digits = contact.phone.replace(/\D/g, '')
    if (digits.length < 9) {
      setError('Укажите телефон для подтверждения записи.')
      return
    }
    if (!contact.consent) {
      setError('Нужно согласие на обработку персональных данных.')
      return
    }
    setSubmitting(true)
    try {
      const appointment = await api<Appointment>('/booking', {
        method: 'POST',
        auth: false,
        body: {
          product_id: selected.id,
          specialist_id: specialistId,
          starts_at: `${date}T${time}:00`,
          customer_name: contact.name.trim(),
          phone: normalizePhoneInput(contact.phone),
          email: contact.email.trim(),
          comment: contact.comment.trim(),
          consent_personal_data: contact.consent,
        },
      })
      setCreated(appointment)
      toast('Запись создана — мы ждём вас', 'success')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Не удалось создать запись'
      setError(message)
      toast(message, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  const cancel = async () => {
    if (!created) return
    setSubmitting(true)
    try {
      await api('/booking/cancel', {
        method: 'POST',
        auth: false,
        body: { number: created.number, phone: created.phone, reason: 'Отменено клиентом на сайте' },
      })
      setCancelled(true)
      toast('Запись отменена', 'info')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось отменить запись', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  if (!site) return null

  if (created) {
    return (
      <div className="container section booking-page">
        <div className="booking-success">
          <span className={`booking-success__icon ${cancelled ? 'is-cancelled' : ''}`}>
            <Icon name={cancelled ? 'close' : 'check'} size={34} />
          </span>
          <span className="eyebrow">{cancelled ? 'Запись отменена' : 'Готово'}</span>
          <h1>{cancelled ? 'Вы отменили запись' : 'Вы записаны'}</h1>
          <p className="booking-success__lead">
            {cancelled
              ? 'Если передумаете — выберите новое время и запишитесь снова.'
              : 'Мы ждём вас в указанное время. Номер записи сохраните — по нему можно перенести или отменить визит.'}
          </p>

          <div className="booking-ticket">
            <div className="booking-ticket__head">
              <div>
                <span>Номер записи</span>
                <strong>{created.number}</strong>
              </div>
              <span className={`badge ${cancelled ? 'badge--muted' : 'badge--fresh'}`}>
                {cancelled ? 'Отменена' : 'Подтверждена'}
              </span>
            </div>
            <dl className="booking-ticket__rows">
              <div><dt>Услуга</dt><dd>{created.service_title}</dd></div>
              {created.specialist_name && (
                <div><dt>Специалист</dt><dd>{created.specialist_name}</dd></div>
              )}
              <div><dt>Когда</dt><dd>{localDateInput(created.starts_at)}</dd></div>
              <div><dt>Длительность</dt><dd>{durationLabel(created.duration_minutes)}</dd></div>
              <div><dt>Стоимость</dt><dd>{formatMoney(created.price)}</dd></div>
              <div><dt>Телефон</dt><dd>{created.phone_formatted || phonePretty(created.phone)}</dd></div>
            </dl>
          </div>

          <div className="booking-success__actions">
            {!cancelled && (
              <button type="button" className="btn btn--outline" onClick={cancel} disabled={submitting}>
                {submitting ? <Spinner size={17} /> : <Icon name="close" size={17} />}
                Отменить запись
              </button>
            )}
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => {
                setCreated(null)
                setCancelled(false)
                setStep(1)
                setTime('')
                setDate('')
                setServiceId(null)
                setSpecialistId(null)
                setContact(CONTACT_EMPTY)
              }}
            >
              <Icon name="calendar" size={17} /> Записаться ещё
            </button>
            <Link to="/" className="btn btn--ghost">На главную</Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="container section booking-page">
      <div className="booking-head">
        <div>
          <div className="breadcrumbs">
            <Link to="/">Главная</Link><Icon name="chevron-right" size={13} />
            <span>Онлайн-запись</span>
          </div>
          <span className="eyebrow">Онлайн-запись</span>
          <h1>Записаться на услугу</h1>
          <p className="booking-head__sub">
            Четыре шага: услуга, специалист, удобное время и контакты. Подтверждение — сразу на экране.
          </p>
        </div>
        <div className="booking-head__outline">
          <Icon name="calendar" size={22} />
          <div>
            <strong>Свободное время онлайн</strong>
            <span>{site.settings.booking_days_ahead} дней вперёд · без звонков</span>
          </div>
        </div>
      </div>

      <ol className="booking-steps">
        {STEPS.map((item) => (
          <li
            key={item.id}
            className={`${step === item.id ? 'is-active' : ''} ${step > item.id ? 'is-done' : ''}`}
          >
            <span className="booking-steps__num">
              {step > item.id ? <Icon name="check" size={15} /> : item.id}
            </span>
            <span>{item.label}</span>
          </li>
        ))}
      </ol>

      {error && (
        <div className="notice notice--error">
          <Icon name="alert" size={18} />
          <span>{error}</span>
        </div>
      )}

      {servicesLoading && !services ? <Loader label="Загружаем услуги…" /> : null}

      {!servicesLoading && !services?.items.length ? (
        <EmptyState
          icon="calendar"
          title="Услуги пока не добавлены"
          text="Как только появятся услуги и специалисты, здесь можно будет записаться онлайн."
          action={<Link to="/contacts" className="btn btn--primary">Связаться с нами</Link>}
        />
      ) : null}

      {services?.items.length ? (
        <div className="booking-layout">
          <div className="booking-wizard">
            <section className={`booking-panel ${step === 1 ? 'is-open' : ''}`}>
              <header className="booking-panel__head">
                <span className="booking-panel__num">01</span>
                <div>
                  <h2>Выберите услугу</h2>
                  <p>Цена и длительность указаны заранее.</p>
                </div>
                {step > 1 && (
                  <button type="button" className="booking-panel__edit" onClick={() => setStep(1)}>
                    Изменить
                  </button>
                )}
              </header>

              {step === 1 && (
                <div className="booking-services">
                  {services.items.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className={`booking-service ${item.id === serviceId ? 'is-active' : ''}`}
                      onClick={() => chooseService(item.id)}
                    >
                      <span className="booking-service__media">
                        {item.image_url
                          ? <img src={assetUrl(item.image_url)} alt="" loading="lazy" />
                          : <Icon name="sparkles" size={22} />}
                      </span>
                      <span className="booking-service__body">
                        <strong>{item.title}</strong>
                        <span className="booking-service__meta">
                          {item.category_title && <>{item.category_title} · </>}
                          {durationLabel(item.duration_minutes)}
                        </span>
                      </span>
                      <span className="booking-service__price">{formatMoney(item.final_price)}</span>
                      <Icon name="chevron-right" size={18} />
                    </button>
                  ))}
                </div>
              )}

              {step > 1 && selected && (
                <div className="booking-chosen">
                  <span className="booking-chosen__icon"><Icon name="sparkles" size={18} /></span>
                  <div>
                    <strong>{selected.title}</strong>
                    <span>{durationLabel(selected.duration_minutes)} · {formatMoney(selected.final_price)}</span>
                  </div>
                </div>
              )}
            </section>

            <section className={`booking-panel ${step === 2 ? 'is-open' : ''}`}>
              <header className="booking-panel__head">
                <span className="booking-panel__num">02</span>
                <div>
                  <h2>Выберите специалиста</h2>
                  <p>Можно доверить выбор первому свободному.</p>
                </div>
                {step > 2 && (
                  <button type="button" className="booking-panel__edit" onClick={() => setStep(2)}>
                    Изменить
                  </button>
                )}
              </header>

              {step === 2 && (
                <>
                  {specialistsLoading ? <Spinner size={20} /> : null}
                  <div className="booking-specialists">
                    <button
                      type="button"
                      className={`booking-specialist booking-specialist--any ${specialistId === null ? 'is-active' : ''}`}
                      onClick={() => chooseSpecialist(null)}
                    >
                      <span className="booking-specialist__photo booking-specialist__photo--any">
                        <Icon name="users" size={22} />
                      </span>
                      <span className="booking-specialist__body">
                        <strong>Любой свободный</strong>
                        <span>Покажем все доступные окна</span>
                      </span>
                      <Icon name="check" size={18} />
                    </button>
                    {specialists?.items.map((person) => (
                      <button
                        key={person.id}
                        type="button"
                        className={`booking-specialist ${specialistId === person.id ? 'is-active' : ''}`}
                        onClick={() => chooseSpecialist(person.id)}
                      >
                        <span className="booking-specialist__photo">
                          {person.photo_url
                            ? <img src={assetUrl(person.photo_url)} alt="" loading="lazy" />
                            : person.name.slice(0, 1)}
                        </span>
                        <span className="booking-specialist__body">
                          <strong>{person.name}</strong>
                          <span>{person.role || 'Специалист'}</span>
                        </span>
                        <Icon name="check" size={18} />
                      </button>
                    ))}
                  </div>
                  {!specialistsLoading && !specialists?.items.length && (
                    <div className="notice">
                      <Icon name="info" size={18} />
                      <span>Запись идёт по общему расписанию — выбирайте любое свободное время.</span>
                    </div>
                  )}
                </>
              )}

              {step > 2 && (
                <div className="booking-chosen">
                  <span className="booking-chosen__icon"><Icon name="user" size={18} /></span>
                  <div>
                    <strong>
                      {specialistId
                        ? specialists?.items.find((item) => item.id === specialistId)?.name ?? 'Специалист'
                        : 'Любой свободный'}
                    </strong>
                    <span>
                      {specialistId
                        ? specialists?.items.find((item) => item.id === specialistId)?.role ?? ''
                        : 'Подберём свободного мастера'}
                    </span>
                  </div>
                </div>
              )}
            </section>

            <section className={`booking-panel ${step === 3 ? 'is-open' : ''}`}>
              <header className="booking-panel__head">
                <span className="booking-panel__num">03</span>
                <div>
                  <h2>Выберите дату и время</h2>
                  <p>Показаны реальные свободные окна.</p>
                </div>
                {step > 3 && (
                  <button type="button" className="booking-panel__edit" onClick={() => setStep(3)}>
                    Изменить
                  </button>
                )}
              </header>

              {step === 3 && (
                <>
                  <div className="booking-days">
                    {days?.days.map((day) => (
                      <button
                        key={day.date}
                        type="button"
                        className={`booking-day ${day.date === date ? 'is-active' : ''}`}
                        disabled={!day.is_open || day.slots_available === 0}
                        onClick={() => setDate(day.date)}
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
                            className={`booking-slot ${slot.time === time ? 'is-active' : ''}`}
                            disabled={!slot.available}
                            onClick={() => {
                              setTime(slot.time)
                              setStep(4)
                            }}
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
                </>
              )}

              {step > 3 && (
                <div className="booking-chosen">
                  <span className="booking-chosen__icon"><Icon name="clock" size={18} /></span>
                  <div>
                    <strong>{humanDate(date)} · {time}</strong>
                    <span>{selected ? durationLabel(selected.duration_minutes) : ''}</span>
                  </div>
                </div>
              )}
            </section>

            <section className={`booking-panel ${step === 4 ? 'is-open' : ''}`}>
              <header className="booking-panel__head">
                <span className="booking-panel__num">04</span>
                <div>
                  <h2>Контакты</h2>
                  <p>Номер записи покажем на экране.</p>
                </div>
              </header>

              {step === 4 && (
                <div className="booking-form">
                  <div className="booking-form__grid">
                    <label className="field">
                      <span className="field__label">Как вас зовут *</span>
                      <input
                        className="input"
                        value={contact.name}
                        onChange={(event) => setContact({ ...contact, name: event.target.value })}
                        placeholder="Имя"
                        autoComplete="name"
                      />
                    </label>
                    <label className="field">
                      <span className="field__label">Телефон *</span>
                      <input
                        className="input"
                        value={contact.phone}
                        onChange={(event) => setContact({ ...contact, phone: phonePretty(event.target.value) })}
                        placeholder="+375 (29) 000-00-00"
                        inputMode="tel"
                        autoComplete="tel"
                      />
                    </label>
                    <label className="field">
                      <span className="field__label">Email</span>
                      <input
                        className="input"
                        type="email"
                        value={contact.email}
                        onChange={(event) => setContact({ ...contact, email: event.target.value })}
                        placeholder="для подтверждения"
                        autoComplete="email"
                      />
                    </label>
                    <label className="field booking-form__full">
                      <span className="field__label">Комментарий</span>
                      <textarea
                        className="input"
                        rows={3}
                        value={contact.comment}
                        onChange={(event) => setContact({ ...contact, comment: event.target.value })}
                        placeholder="Пожелания или вопрос к специалисту"
                      />
                    </label>
                  </div>

                  <label className="checkbox booking-form__consent">
                    <input
                      type="checkbox"
                      checked={contact.consent}
                      onChange={(event) => setContact({ ...contact, consent: event.target.checked })}
                    />
                    <span>
                      Согласен на обработку персональных данных для оформления записи
                      {' '}
                      <Link to="/legal/privacy" target="_blank">политика конфиденциальности</Link>.
                    </span>
                  </label>

                  <button
                    type="button"
                    className="btn btn--primary btn--lg btn--block"
                    disabled={submitting || !contact.consent || !time}
                    onClick={submit}
                  >
                    {submitting ? <Spinner size={18} /> : <Icon name="check" size={18} />}
                    Подтвердить запись
                  </button>
                </div>
              )}
            </section>
          </div>

          <aside className="booking-summary">
            <div className="booking-summary__head">
              <span className="eyebrow">Ваша запись</span>
              <strong>{selected?.title ?? 'Выберите услугу'}</strong>
            </div>
            <dl className="booking-summary__rows">
              <div>
                <dt><Icon name="users" size={16} /> Специалист</dt>
                <dd>
                  {specialistId
                    ? specialists?.items.find((item) => item.id === specialistId)?.name ?? '—'
                    : 'Любой свободный'}
                </dd>
              </div>
              <div>
                <dt><Icon name="calendar" size={16} /> Дата</dt>
                <dd>{date ? humanDate(date) : '—'}</dd>
              </div>
              <div>
                <dt><Icon name="clock" size={16} /> Время</dt>
                <dd>{time || '—'}</dd>
              </div>
              <div>
                <dt><Icon name="wallet" size={16} /> Стоимость</dt>
                <dd>{selected ? formatMoney(selected.final_price) : '—'}</dd>
              </div>
            </dl>
            <div className="booking-summary__note">
              <Icon name="info" size={16} />
              <span>Оплата на месте после услуги. Отменить запись можно по номеру на сайте.</span>
            </div>
            {site.settings.phone && (
              <a href={`tel:${site.settings.phone.replace(/[^\d+]/g, '')}`} className="booking-summary__phone">
                <Icon name="phone" size={16} /> {site.settings.phone}
              </a>
            )}
          </aside>
        </div>
      ) : null}

      {step > 1 && (
        <button
          type="button"
          className="booking-back"
          onClick={() => setStep((current) => Math.max(1, current - 1))}
        >
          <Icon name="arrow-left" size={17} /> Назад
        </button>
      )}

      <p className="booking-hint">
        Запись открыта на {site.settings.booking_days_ahead} дней вперёд.
        {days?.days?.length ? ` Ближайший свободный день — ${humanDate(
          days.days.find((day) => day.slots_available > 0)?.date ?? addDaysIso(site.today.date, 1),
        )}.` : ''}
      </p>
    </div>
  )
}
