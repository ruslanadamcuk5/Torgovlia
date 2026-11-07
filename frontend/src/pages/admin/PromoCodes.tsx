import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Loader, Spinner } from '../../components/ui'
import { Icon } from '../../components/icons'
import type { PromoCode } from '../../lib/types'
import { formatMoney } from '../../lib/format'

interface PromoForm {
  code: string
  kind: 'percent' | 'fixed'
  value: string
  min_order: string
  max_uses: string
  is_active: boolean
  note: string
}

const EMPTY: PromoForm = {
  code: '',
  kind: 'percent',
  value: '10',
  min_order: '0',
  max_uses: '0',
  is_active: true,
  note: '',
}

const STATUS_LABEL: Record<string, { label: string; tone: string }> = {
  active: { label: 'Активен', tone: 'success' },
  scheduled: { label: 'Запланирован', tone: 'info' },
  expired: { label: 'Истёк', tone: 'muted' },
  used_up: { label: 'Лимит исчерпан', tone: 'warning' },
  disabled: { label: 'Отключён', tone: 'muted' },
}

export default function PromoCodes() {
  const { toast } = useToast()
  const { data: features, loading: featuresLoading } = useApi<{ services: Record<string, boolean> }>('/admin/services/features')
  const enabled = Boolean(features?.services.promo_codes)
  const { data, loading, reload } = useApi<PromoCode[]>(enabled ? '/admin/promo-codes' : null)
  const [form, setForm] = useState<PromoForm>(EMPTY)
  const [editing, setEditing] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const codes = data ?? []

  const set = <K extends keyof PromoForm>(key: K, value: PromoForm[K]) => {
    setForm((current) => ({ ...current, [key]: value }))
  }

  const reset = () => {
    setForm(EMPTY)
    setEditing(null)
    setError('')
  }

  const startEdit = (promo: PromoCode) => {
    setEditing(promo.id)
    setError('')
    setForm({
      code: promo.code,
      kind: promo.kind,
      value: String(promo.value),
      min_order: String(promo.min_order),
      max_uses: String(promo.max_uses),
      is_active: promo.is_active,
      note: promo.note,
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const save = async () => {
    const code = form.code.trim()
    if (!/^[A-Za-z0-9][A-Za-z0-9_-]{1,31}$/.test(code)) {
      return setError('Код: латиница, цифры, дефис или подчёркивание, от 2 до 32 символов')
    }
    const value = Number(form.value)
    if (!(value > 0)) return setError('Укажите размер скидки больше нуля')
    if (form.kind === 'percent' && value > 95) return setError('Процентная скидка не может быть больше 95%')

    setBusy(true)
    setError('')
    try {
      const payload = {
        code: code.toUpperCase(),
        kind: form.kind,
        value,
        min_order: Math.max(0, Number(form.min_order) || 0),
        max_uses: Math.max(0, Math.round(Number(form.max_uses) || 0)),
        is_active: form.is_active,
        note: form.note.trim(),
      }
      if (editing) {
        await api(`/admin/promo-codes/${editing}`, { method: 'PUT', body: payload })
        toast(`Промокод ${payload.code} обновлён`)
      } else {
        await api('/admin/promo-codes', { method: 'POST', body: payload })
        toast(`Промокод ${payload.code} создан`)
      }
      reset()
      reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось сохранить промокод')
    } finally {
      setBusy(false)
    }
  }

  const toggle = async (promo: PromoCode) => {
    setBusy(true)
    try {
      await api(`/admin/promo-codes/${promo.id}`, {
        method: 'PUT',
        body: {
          code: promo.code,
          kind: promo.kind,
          value: promo.value,
          min_order: promo.min_order,
          max_uses: promo.max_uses,
          is_active: !promo.is_active,
          note: promo.note,
        },
      })
      toast(promo.is_active ? 'Промокод отключён' : 'Промокод включён')
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить промокод', 'error')
    } finally {
      setBusy(false)
    }
  }

  const remove = async (promo: PromoCode) => {
    if (!window.confirm(`Удалить промокод ${promo.code}?`)) return
    setBusy(true)
    try {
      await api(`/admin/promo-codes/${promo.id}`, { method: 'DELETE' })
      toast('Промокод удалён')
      if (editing === promo.id) reset()
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось удалить промокод', 'error')
    } finally {
      setBusy(false)
    }
  }

  if (featuresLoading) return <Loader />

  if (!enabled) {
    return (
      <div className="admin-page">
        <section className="panel panel--accent">
          <div className="panel__head"><h2>Промокоды</h2></div>
          <p>
            Промокоды и скидки на бронь доступны на тарифе <strong>«Бизнес»</strong> и выше.
            Включите сервис в разделе «Сервисы» — после этого здесь появится управление кодами.
          </p>
          <Link to="/admin/services" className="btn btn--primary">Перейти к сервисам <Icon name="arrow-right" size={17} /></Link>
        </section>
      </div>
    )
  }

  if (loading) return <Loader />

  return (
    <div className="admin-page promo-codes-page">
      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>{editing ? 'Изменить промокод' : 'Новый промокод'}</h2>
            <p className="muted">Скидка применяется к сумме брони при оформлении. Лимит использований считается по заказам.</p>
          </div>
          {editing && <button type="button" className="btn btn--ghost btn--sm" onClick={reset}>Отменить</button>}
        </div>

        <div className="promo-form">
          <label className="field">
            <span className="field__label">Код</span>
            <input
              className="input"
              value={form.code}
              onChange={(event) => set('code', event.target.value.toUpperCase())}
              placeholder="ВЕСНА10"
              maxLength={32}
            />
          </label>
          <label className="field">
            <span className="field__label">Тип скидки</span>
            <select className="input input--select" value={form.kind} onChange={(event) => set('kind', event.target.value as 'percent' | 'fixed')}>
              <option value="percent">Процент от суммы</option>
              <option value="fixed">Фиксированная сумма, BYN</option>
            </select>
          </label>
          <label className="field">
            <span className="field__label">{form.kind === 'percent' ? 'Скидка, %' : 'Скидка, BYN'}</span>
            <input className="input" type="number" min="0" step="0.01" value={form.value} onChange={(event) => set('value', event.target.value)} />
          </label>
          <label className="field">
            <span className="field__label">Минимальная сумма, BYN</span>
            <input className="input" type="number" min="0" step="0.01" value={form.min_order} onChange={(event) => set('min_order', event.target.value)} />
          </label>
          <label className="field">
            <span className="field__label">Лимит использований</span>
            <input className="input" type="number" min="0" step="1" value={form.max_uses} onChange={(event) => set('max_uses', event.target.value)} />
            <span className="field__hint">0 — без ограничения</span>
          </label>
          <label className="field">
            <span className="field__label">Комментарий</span>
            <input className="input" value={form.note} onChange={(event) => set('note', event.target.value)} placeholder="Например: весенняя акция" maxLength={200} />
          </label>
        </div>

        <label className="switch-row promo-form__switch">
          <span>Промокод активен</span>
          <input type="checkbox" checked={form.is_active} onChange={(event) => set('is_active', event.target.checked)} />
          <span className="switch" />
        </label>

        {error && <div className="notice notice--error"><Icon name="alert" size={18} /><span>{error}</span></div>}

        <div className="promo-form__actions">
          <button type="button" className="btn btn--primary" onClick={save} disabled={busy}>
            {busy ? <Spinner size={17} /> : <Icon name="check" size={17} />}
            {editing ? 'Сохранить изменения' : 'Создать промокод'}
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <h2>Все промокоды</h2>
          <span className="muted">{codes.length} шт.</span>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Код</th>
                <th>Скидка</th>
                <th>Условия</th>
                <th>Использовано</th>
                <th>Статус</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {codes.map((promo) => {
                const state = STATUS_LABEL[promo.status] ?? STATUS_LABEL.disabled
                return (
                  <tr key={promo.id} className={promo.is_active ? '' : 'is-muted'}>
                    <td><strong>{promo.code}</strong>{promo.note && <span className="table-sub">{promo.note}</span>}</td>
                    <td>{promo.kind === 'percent' ? `${promo.value}%` : formatMoney(promo.value)}</td>
                    <td>
                      <span className="table-sub">
                        от {formatMoney(promo.min_order)}
                        {promo.max_uses ? ` · лимит ${promo.max_uses}` : ' · без лимита'}
                      </span>
                    </td>
                    <td>{promo.used_count}{promo.max_uses ? ` / ${promo.max_uses}` : ''}</td>
                    <td><span className={`badge badge--${state.tone}`}>{state.label}</span></td>
                    <td>
                      <div className="promo-actions">
                        <button type="button" className="btn btn--sm btn--ghost" onClick={() => startEdit(promo)} disabled={busy}>
                          Изменить
                        </button>
                        <button type="button" className="btn btn--sm btn--ghost" onClick={() => void toggle(promo)} disabled={busy}>
                          {promo.is_active ? 'Отключить' : 'Включить'}
                        </button>
                        <button type="button" className="btn btn--sm btn--ghost" onClick={() => void remove(promo)} disabled={busy || promo.used_count > 0}>
                          Удалить
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {codes.length === 0 && <p className="muted">Промокодов пока нет — создайте первый.</p>}
      </section>
    </div>
  )
}
