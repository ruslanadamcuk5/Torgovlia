import { useEffect, useMemo, useState } from 'react'
import { useApi } from '../../lib/useApi'
import { api, assetUrl } from '../../lib/api'
import { useToast } from '../../store/ToastContext'
import { Loader, Modal, Spinner } from '../../components/ui'
import { Icon } from '../../components/icons'
import type { Product, Specialist, WorkingDay } from '../../lib/types'
import { weekdayShortByIndex } from '../../lib/format'

const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

function defaultHours(): WorkingDay[] {
  return WEEKDAYS.map((label, weekday) => ({
    weekday,
    label,
    open: '10:00',
    close: '19:00',
    closed: weekday === 6,
  }))
}

interface FormState {
  id: number | null
  name: string
  role: string
  bio: string
  photo_url: string
  phone: string
  email: string
  color: string
  service_ids: number[]
  customHours: boolean
  working_hours: WorkingDay[]
  time_off: string[]
  is_active: boolean
}

const EMPTY: FormState = {
  id: null,
  name: '',
  role: '',
  bio: '',
  photo_url: '',
  phone: '',
  email: '',
  color: '',
  service_ids: [],
  customHours: false,
  working_hours: defaultHours(),
  time_off: [],
  is_active: true,
}

export default function AdminSpecialists() {
  const { toast } = useToast()
  const { data, loading, reload } = useApi<{ items: Specialist[] }>('/admin/specialists')
  const { data: services } = useApi<{ items: Product[] }>('/services?limit=100', false)

  const [form, setForm] = useState<FormState | null>(null)
  const [busy, setBusy] = useState(false)
  const [offDate, setOffDate] = useState('')

  const rows = data?.items ?? []
  const activeCount = useMemo(() => rows.filter((item) => item.is_active).length, [rows])

  const openNew = () => setForm({ ...EMPTY, working_hours: defaultHours(), time_off: [] })

  const openEdit = (person: Specialist) => setForm({
    id: person.id,
    name: person.name,
    role: person.role,
    bio: person.bio,
    photo_url: person.photo_url ?? '',
    phone: person.phone,
    email: person.email ?? '',
    color: person.color,
    service_ids: person.service_ids ?? [],
    customHours: (person.working_hours ?? []).length > 0,
    working_hours: (person.working_hours ?? []).length > 0
      ? WEEKDAYS.map((label, weekday) => {
        const found = person.working_hours.find((day) => day.weekday === weekday)
        return found ?? { weekday, label, open: '10:00', close: '19:00', closed: true }
      })
      : defaultHours(),
    time_off: person.time_off ?? [],
    is_active: person.is_active,
  })

  const toggleService = (id: number) => {
    if (!form) return
    const exists = form.service_ids.includes(id)
    setForm({
      ...form,
      service_ids: exists
        ? form.service_ids.filter((item) => item !== id)
        : [...form.service_ids, id],
    })
  }

  const updateDay = (index: number, patch: Partial<WorkingDay>) => {
    if (!form) return
    setForm({
      ...form,
      working_hours: form.working_hours.map((day, dayIndex) => (
        dayIndex === index ? { ...day, ...patch } : day
      )),
    })
  }

  const save = async () => {
    if (!form) return
    if (form.name.trim().length < 2) {
      toast('Укажите имя специалиста', 'error')
      return
    }
    setBusy(true)
    const body: Record<string, unknown> = {
      name: form.name.trim(),
      role: form.role.trim(),
      bio: form.bio.trim(),
      photo_url: form.photo_url.trim() || null,
      phone: form.phone.trim(),
      email: form.email.trim() || null,
      color: form.color,
      service_ids: form.service_ids,
      working_hours: form.customHours ? form.working_hours : [],
      time_off: form.time_off,
      is_active: form.is_active,
    }
    try {
      if (form.id) {
        await api(`/admin/specialists/${form.id}`, { method: 'PATCH', body })
        toast('Специалист сохранён')
      } else {
        await api('/admin/specialists', { method: 'POST', body })
        toast('Специалист добавлен')
      }
      setForm(null)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить специалиста', 'error')
    } finally {
      setBusy(false)
    }
  }

  const disable = async (person: Specialist) => {
    if (!confirm(`Скрыть ${person.name} из записи?`)) return
    try {
      await api(`/admin/specialists/${person.id}`, { method: 'DELETE' })
      toast('Специалист скрыт')
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось скрыть специалиста', 'error')
    }
  }

  const restore = async (person: Specialist) => {
    try {
      await api(`/admin/specialists/${person.id}`, { method: 'PATCH', body: { is_active: true } })
      toast('Специалист снова в записи')
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось вернуть специалиста', 'error')
    }
  }

  const addDayOff = () => {
    if (!form || !offDate) return
    if (form.time_off.includes(offDate)) return
    setForm({ ...form, time_off: [...form.time_off, offDate].sort() })
    setOffDate('')
  }

  return (
    <div className="admin-page">
      <div className="admin-toolbar">
        <div className="admin-toolbar__left">
          <span className="muted">
            {rows.length} специалистов · активных {activeCount}
          </span>
        </div>
        <div className="admin-toolbar__right">
          <button type="button" className="btn btn--sm btn--primary" onClick={openNew}>
            <Icon name="plus" size={16} /> Добавить специалиста
          </button>
        </div>
      </div>

      {loading ? <Loader /> : rows.length ? (
        <div className="specialist-admin-grid">
          {rows.map((person) => (
            <article className={`panel specialist-admin ${person.is_active ? '' : 'is-inactive'}`} key={person.id}>
              <div className="specialist-admin__head">
                <span className="specialist-admin__photo">
                  {person.photo_url
                    ? <img src={assetUrl(person.photo_url)} alt="" />
                    : person.name.slice(0, 1)}
                </span>
                <div>
                  <strong>{person.name}</strong>
                  <span>{person.role || 'Специалист'}</span>
                </div>
                <span className={`badge badge--${person.is_active ? 'fresh' : 'muted'}`}>
                  {person.is_active ? 'в записи' : 'скрыт'}
                </span>
              </div>

              <div className="specialist-admin__meta">
                <span><Icon name="sparkles" size={15} /> {person.services.length || 'все услуги'}</span>
                <span><Icon name="calendar" size={15} /> {(person.working_hours ?? []).length ? 'свой график' : 'график заведения'}</span>
                {person.time_off.length > 0 && (
                  <span><Icon name="clock" size={15} /> отсутствует: {person.time_off.length}</span>
                )}
              </div>

              {person.services.length > 0 && (
                <div className="specialist-admin__services">
                  {person.services.slice(0, 4).map((service) => (
                    <span key={service.id}>{service.title}</span>
                  ))}
                  {person.services.length > 4 && <span>+{person.services.length - 4}</span>}
                </div>
              )}

              <div className="specialist-admin__actions">
                <button type="button" className="btn btn--sm btn--outline" onClick={() => openEdit(person)}>
                  <Icon name="edit" size={15} /> Изменить
                </button>
                {person.is_active ? (
                  <button type="button" className="btn btn--sm btn--ghost" onClick={() => disable(person)}>
                    Скрыть
                  </button>
                ) : (
                  <button type="button" className="btn btn--sm btn--ghost" onClick={() => restore(person)}>
                    Вернуть
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <span className="empty-state__icon"><Icon name="users" size={28} /></span>
          <h3>Специалистов пока нет</h3>
          <p>Добавьте мастеров — и клиенты смогут выбрать конкретного человека при записи.</p>
          <button type="button" className="btn btn--primary" onClick={openNew}>
            <Icon name="plus" size={16} /> Добавить специалиста
          </button>
        </div>
      )}

      {form && (
        <Modal
          title={form.id ? `Специалист: ${form.name || 'без имени'}` : 'Новый специалист'}
          subtitle="Карточка, услуги и график"
          onClose={() => setForm(null)}
          size="lg"
          footer={(
            <>
              <button type="button" className="btn btn--ghost" onClick={() => setForm(null)}>Отмена</button>
              <button type="button" className="btn btn--primary" disabled={busy} onClick={save}>
                {busy ? <Spinner size={16} /> : <Icon name="check" size={16} />}
                Сохранить
              </button>
            </>
          )}
        >
          <div className="booking-form">
            <div className="booking-form__grid">
              <label className="field">
                <span className="field__label">Имя *</span>
                <input
                  className="input"
                  value={form.name}
                  onChange={(event) => setForm({ ...form, name: event.target.value })}
                  placeholder="Анна"
                />
              </label>
              <label className="field">
                <span className="field__label">Должность</span>
                <input
                  className="input"
                  value={form.role}
                  onChange={(event) => setForm({ ...form, role: event.target.value })}
                  placeholder="Стилист-парикмахер"
                />
              </label>
              <label className="field">
                <span className="field__label">Телефон</span>
                <input
                  className="input"
                  value={form.phone}
                  onChange={(event) => setForm({ ...form, phone: event.target.value })}
                  placeholder="+375 (29) 000-00-00"
                />
              </label>
              <label className="field">
                <span className="field__label">Email</span>
                <input
                  className="input"
                  value={form.email}
                  onChange={(event) => setForm({ ...form, email: event.target.value })}
                  placeholder="master@example.by"
                />
              </label>
              <label className="field booking-form__full">
                <span className="field__label">Фото (ссылка)</span>
                <input
                  className="input"
                  value={form.photo_url}
                  onChange={(event) => setForm({ ...form, photo_url: event.target.value })}
                  placeholder="/uploads/master.jpg"
                />
              </label>
              <label className="field booking-form__full">
                <span className="field__label">О специалисте</span>
                <textarea
                  className="textarea"
                  rows={3}
                  value={form.bio}
                  onChange={(event) => setForm({ ...form, bio: event.target.value })}
                  placeholder="Опыт, специализация и подход"
                />
              </label>
            </div>

            <div className="specialist-services">
              <span className="field__label">Услуги специалиста</span>
              <p className="muted">Ничего не выбрано — специалист оказывает все услуги.</p>
              <div className="specialist-services__grid">
                {services?.items.map((service) => (
                  <label
                    key={service.id}
                    className={`checkbox-card ${form.service_ids.includes(service.id) ? 'is-active' : ''}`}
                  >
                    <input
                      type="checkbox"
                      checked={form.service_ids.includes(service.id)}
                      onChange={() => toggleService(service.id)}
                    />
                    <span>
                      <strong>{service.title}</strong>
                      <em>{service.duration_minutes} мин</em>
                    </span>
                  </label>
                ))}
              </div>
            </div>

            <div className="specialist-hours">
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={form.customHours}
                  onChange={(event) => setForm({ ...form, customHours: event.target.checked })}
                />
                <span>Свой график (иначе работает по часам заведения)</span>
              </label>

              {form.customHours && (
                <div className="hours-editor">
                  {form.working_hours.map((day, index) => (
                    <div className={`hours-editor__row ${day.closed ? 'is-closed' : ''}`} key={day.weekday}>
                      <strong>{weekdayShortByIndex(day.weekday)}</strong>
                      <label className="checkbox checkbox--inline">
                        <input
                          type="checkbox"
                          checked={day.closed}
                          onChange={(event) => updateDay(index, { closed: event.target.checked })}
                        />
                        <span>выходной</span>
                      </label>
                      <input
                        className="input input--sm"
                        type="time"
                        value={day.open}
                        disabled={day.closed}
                        onChange={(event) => updateDay(index, { open: event.target.value })}
                      />
                      <span>—</span>
                      <input
                        className="input input--sm"
                        type="time"
                        value={day.close}
                        disabled={day.closed}
                        onChange={(event) => updateDay(index, { close: event.target.value })}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="specialist-timeoff">
              <span className="field__label">Дни отсутствия</span>
              <div className="specialist-timeoff__add">
                <input
                  className="input input--sm"
                  type="date"
                  value={offDate}
                  onChange={(event) => setOffDate(event.target.value)}
                />
                <button type="button" className="btn btn--sm btn--outline" onClick={addDayOff}>
                  <Icon name="plus" size={15} /> Добавить
                </button>
              </div>
              {form.time_off.length > 0 ? (
                <div className="specialist-timeoff__list">
                  {form.time_off.map((day) => (
                    <span key={day} className="badge badge--muted">
                      {day}
                      <button
                        type="button"
                        aria-label="Удалить"
                        onClick={() => setForm({
                          ...form,
                          time_off: form.time_off.filter((item) => item !== day),
                        })}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              ) : (
                <p className="muted">Отпуск и выходные, когда специалист не принимает.</p>
              )}
            </div>

            <label className="checkbox">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
              />
              <span>Показывать специалиста на сайте и в записи</span>
            </label>
          </div>
        </Modal>
      )}
    </div>
  )
}
