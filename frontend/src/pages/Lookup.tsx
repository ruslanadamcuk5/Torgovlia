import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useSite } from '../store/SettingsContext'
import { OrderCard, StatusTimeline } from '../components/OrderCard'
import { Spinner } from '../components/ui'
import { Icon } from '../components/icons'
import type { Order } from '../lib/types'
import { normalizePhoneInput, phonePretty } from '../lib/format'

export default function Lookup() {
  const { site } = useSite()
  const [number, setNumber] = useState('')
  const [phone, setPhone] = useState('')
  const [order, setOrder] = useState<Order | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!site) return null

  const search = async () => {
    setError('')
    setOrder(null)
    if (!number.trim()) return setError('Введите номер заказа')
    if (phone.replace(/\D/g, '').length < 9) return setError('Введите телефон, указанный при оформлении заказа')
    setBusy(true)
    try {
      const result = await api<Order>('/orders/lookup', {
        method: 'POST',
        body: { number: number.trim().toUpperCase(), phone },
        auth: false,
      })
      setOrder(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Заказ не найден')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="container section">
      <div className="breadcrumbs"><Link to="/">Главная</Link><Icon name="chevron-right" size={13} /><span>Найти заказ</span></div>
      <div className="page-head page-head--compact">
        <span className="eyebrow">Без регистрации</span>
        <h1>Найти заказ</h1>
        <p className="page-head__sub">Введите номер заказа и телефон, указанный при оформлении.</p>
      </div>

      <div className="lookup-grid">
        <div className="panel">
          <label className="field">
            <span className="field__label">Номер заказа</span>
            <input
              className="input"
              value={number}
              onChange={(event) => setNumber(event.target.value.toUpperCase())}
              placeholder="RL-261102-1234"
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
          {error && <div className="notice notice--error"><Icon name="alert" size={17} /><span>{error}</span></div>}
          <button type="button" className="btn btn--primary btn--lg btn--block" onClick={search} disabled={busy}>
            {busy ? <Spinner size={18} /> : <Icon name="search" size={18} />} Найти
          </button>
          <p className="field__hint">Номер заказа приходит в SMS сразу после оформления. Если SMS не пришло — позвоните в магазин.</p>
        </div>

        <div className="panel panel--soft">
          <h3><Icon name="info" size={19} /> Как это работает</h3>
          <p>Заказ можно найти без входа в аккаунт: достаточно номера заказа и телефона. Данные видны только тому, кто знает оба значения.</p>
          <div className="notice">
            <Icon name="pin" size={18} />
            <span>{site.settings.city}, {site.settings.market_name}, {site.settings.pavilion}. Заберите заказ к выбранному времени.</span>
          </div>
          <Link to="/login" className="link-arrow">Войти в личный кабинет <Icon name="arrow-right" size={16} /></Link>
        </div>
      </div>

      {order && (
        <section className="lookup-result">
          <h2>Заказ найден</h2>
          <OrderCard order={order} />
          <StatusTimeline order={order} />
          <p className="muted">Для отмены или изменения заказа позвоните в магазин: {site.settings.phone}</p>
        </section>
      )}
    </div>
  )
}
