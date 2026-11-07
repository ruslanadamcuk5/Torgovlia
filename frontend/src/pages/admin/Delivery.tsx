import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Loader, Spinner } from '../../components/ui'
import { Icon } from '../../components/icons'
import type { DeliveryZone } from '../../lib/types'
import { formatMoney } from '../../lib/format'

interface ZoneForm {
  name: string
  areas: string
  fee: string
  min_order: string
  free_from: string
  eta: string
  is_active: boolean
  sort_order: string
}

const EMPTY: ZoneForm = {
  name: '',
  areas: '',
  fee: '5',
  min_order: '20',
  free_from: '80',
  eta: '1–2 часа',
  is_active: true,
  sort_order: '10',
}

export default function Delivery() {
  const { toast } = useToast()
  const { data: features, loading: featuresLoading } = useApi<{ services: Record<string, boolean> }>('/admin/services/features')
  const enabled = Boolean(features?.services.delivery)
  const { data, loading, reload } = useApi<DeliveryZone[]>(enabled ? '/admin/delivery/zones' : null)
  const [form, setForm] = useState<ZoneForm>(EMPTY)
  const [editing, setEditing] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const zones = data ?? []

  const set = <K extends keyof ZoneForm>(key: K, value: ZoneForm[K]) => {
    setForm((current) => ({ ...current, [key]: value }))
  }

  const reset = () => {
    setForm(EMPTY)
    setEditing(null)
    setError('')
  }

  const startEdit = (zone: DeliveryZone) => {
    setEditing(zone.id)
    setError('')
    setForm({
      name: zone.name,
      areas: zone.areas,
      fee: String(zone.fee),
      min_order: String(zone.min_order),
      free_from: String(zone.free_from),
      eta: zone.eta,
      is_active: zone.is_active,
      sort_order: String(zone.sort_order),
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const save = async () => {
    if (form.name.trim().length < 2) return setError('Название зоны — хотя бы 2 символа')
    setBusy(true)
    setError('')
    try {
      const payload = {
        name: form.name.trim(),
        areas: form.areas.trim(),
        fee: Math.max(0, Number(form.fee) || 0),
        min_order: Math.max(0, Number(form.min_order) || 0),
        free_from: Math.max(0, Number(form.free_from) || 0),
        eta: form.eta.trim(),
        is_active: form.is_active,
        sort_order: Math.max(0, Math.round(Number(form.sort_order) || 0)),
      }
      if (editing) {
        await api(`/admin/delivery/zones/${editing}`, { method: 'PUT', body: payload })
        toast(`Зона «${payload.name}» обновлена`)
      } else {
        await api('/admin/delivery/zones', { method: 'POST', body: payload })
        toast(`Зона «${payload.name}» создана`)
      }
      reset()
      reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось сохранить зону')
    } finally {
      setBusy(false)
    }
  }

  const toggle = async (zone: DeliveryZone) => {
    setBusy(true)
    try {
      await api(`/admin/delivery/zones/${zone.id}`, {
        method: 'PUT',
        body: {
          name: zone.name,
          areas: zone.areas,
          fee: zone.fee,
          min_order: zone.min_order,
          free_from: zone.free_from,
          eta: zone.eta,
          is_active: !zone.is_active,
          sort_order: zone.sort_order,
        },
      })
      toast(zone.is_active ? 'Зона отключена' : 'Зона включена')
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить зону', 'error')
    } finally {
      setBusy(false)
    }
  }

  const remove = async (zone: DeliveryZone) => {
    if (!window.confirm(`Удалить зону «${zone.name}»?`)) return
    setBusy(true)
    try {
      await api(`/admin/delivery/zones/${zone.id}`, { method: 'DELETE' })
      toast('Зона удалена')
      if (editing === zone.id) reset()
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось удалить зону', 'error')
    } finally {
      setBusy(false)
    }
  }

  if (featuresLoading) return <Loader />

  if (!enabled) {
    return (
      <div className="admin-page">
        <section className="panel panel--accent">
          <div className="panel__head"><h2>Доставка</h2></div>
          <p>
            Доставка доступна на тарифе <strong>«Бизнес»</strong> и выше.
            Включите сервис в разделе «Сервисы» — после этого здесь появятся зоны и стоимость.
          </p>
          <Link to="/admin/services" className="btn btn--primary">Перейти к сервисам <Icon name="arrow-right" size={17} /></Link>
        </section>
      </div>
    )
  }

  if (loading) return <Loader />

  return (
    <div className="admin-page delivery-page">
      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>{editing ? 'Изменить зону' : 'Новая зона доставки'}</h2>
            <p className="muted">
              Покупатель выбирает зону при оформлении. Стоимость добавляется к сумме заказа,
              а от порога бесплатной доставки обнуляется.
            </p>
          </div>
          {editing && <button type="button" className="btn btn--ghost btn--sm" onClick={reset}>Отменить</button>}
        </div>

        <div className="promo-form">
          <label className="field">
            <span className="field__label">Название</span>
            <input className="input" value={form.name} onChange={(event) => set('name', event.target.value)} placeholder="Барановичи" maxLength={80} />
          </label>
          <label className="field">
            <span className="field__label">Районы и адреса</span>
            <input className="input" value={form.areas} onChange={(event) => set('areas', event.target.value)} placeholder="г. Барановичи" maxLength={1000} />
          </label>
          <label className="field">
            <span className="field__label">Стоимость, BYN</span>
            <input className="input" type="number" min="0" step="0.01" value={form.fee} onChange={(event) => set('fee', event.target.value)} />
          </label>
          <label className="field">
            <span className="field__label">Минимальный заказ, BYN</span>
            <input className="input" type="number" min="0" step="0.01" value={form.min_order} onChange={(event) => set('min_order', event.target.value)} />
          </label>
          <label className="field">
            <span className="field__label">Бесплатно от, BYN</span>
            <input className="input" type="number" min="0" step="0.01" value={form.free_from} onChange={(event) => set('free_from', event.target.value)} />
            <span className="field__hint">0 — бесплатной доставки нет</span>
          </label>
          <label className="field">
            <span className="field__label">Срок доставки</span>
            <input className="input" value={form.eta} onChange={(event) => set('eta', event.target.value)} placeholder="1–2 часа" maxLength={60} />
          </label>
          <label className="field">
            <span className="field__label">Порядок</span>
            <input className="input" type="number" min="0" step="1" value={form.sort_order} onChange={(event) => set('sort_order', event.target.value)} />
          </label>
        </div>

        <label className="switch-row promo-form__switch">
          <span>Зона активна</span>
          <input type="checkbox" checked={form.is_active} onChange={(event) => set('is_active', event.target.checked)} />
          <span className="switch" />
        </label>

        {error && <div className="notice notice--error"><Icon name="alert" size={18} /><span>{error}</span></div>}

        <div className="promo-form__actions">
          <button type="button" className="btn btn--primary" onClick={save} disabled={busy}>
            {busy ? <Spinner size={17} /> : <Icon name="check" size={17} />}
            {editing ? 'Сохранить изменения' : 'Создать зону'}
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <h2>Зоны доставки</h2>
          <span className="muted">{zones.length} шт.</span>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Зона</th>
                <th>Стоимость</th>
                <th>Условия</th>
                <th>Срок</th>
                <th>Статус</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {zones.map((zone) => (
                <tr key={zone.id} className={zone.is_active ? '' : 'is-muted'}>
                  <td>
                    <strong>{zone.name}</strong>
                    {zone.areas && <span className="table-sub">{zone.areas}</span>}
                  </td>
                  <td><strong>{formatMoney(zone.fee)}</strong></td>
                  <td>
                    <span className="table-sub">
                      от {formatMoney(zone.min_order)}
                      {zone.free_from > 0 ? ` · бесплатно от ${formatMoney(zone.free_from)}` : ' · без бесплатной'}
                    </span>
                  </td>
                  <td>{zone.eta || '—'}</td>
                  <td>
                    <span className={`badge badge--${zone.is_active ? 'success' : 'muted'}`}>
                      {zone.is_active ? 'Активна' : 'Отключена'}
                    </span>
                  </td>
                  <td>
                    <div className="promo-actions">
                      <button type="button" className="btn btn--sm btn--ghost" onClick={() => startEdit(zone)} disabled={busy}>Изменить</button>
                      <button type="button" className="btn btn--sm btn--ghost" onClick={() => void toggle(zone)} disabled={busy}>
                        {zone.is_active ? 'Отключить' : 'Включить'}
                      </button>
                      <button type="button" className="btn btn--sm btn--ghost" onClick={() => void remove(zone)} disabled={busy}>Удалить</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {zones.length === 0 && <p className="muted">Зон пока нет — добавьте первую, чтобы включить доставку на витрине.</p>}
      </section>
    </div>
  )
}
