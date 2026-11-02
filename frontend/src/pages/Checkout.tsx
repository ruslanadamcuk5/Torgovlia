import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useSite } from '../store/SettingsContext'
import { useCart } from '../store/CartContext'
import { useAuth } from '../store/AuthContext'
import { useToast } from '../store/ToastContext'
import { useApi } from '../lib/useApi'
import { api, assetUrl } from '../lib/api'
import { SmsVerify } from '../components/SmsVerify'
import { Spinner, EmptyState } from '../components/ui'
import { Icon } from '../components/icons'
import type { Order, Slots } from '../lib/types'
import {
  addDaysIso, formatMoney, formatQty, humanDate, normalizePhoneInput, phonePretty, samePhone, unitShort, weekdayShort,
} from '../lib/format'

export default function Checkout() {
  const { site } = useSite()
  const { lines, subtotal, clear, count } = useCart()
  const { user } = useAuth()
  const { toast } = useToast()
  const navigate = useNavigate()

  const [name, setName] = useState(user?.full_name ?? '')
  const [phone, setPhone] = useState(user?.phone ?? '')
  const [comment, setComment] = useState('')
  const [date, setDate] = useState('')
  const [time, setTime] = useState('')
  const [phoneToken, setPhoneToken] = useState('')
  const [verifiedPhone, setVerifiedPhone] = useState('')
  const [consent, setConsent] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [created, setCreated] = useState<Order | null>(null)

  const s = site?.settings
  const hour = 60 * 60 * 1000

  const dates = useMemo(() => {
    if (!s || !site) return []
    const result: { iso: string; closed: boolean; label: string }[] = []
    for (let index = 0; index < Math.min(14, s.booking_days_ahead + 1); index += 1) {
      const iso = addDaysIso(site.today.date, index)
      const weekday = new Date(`${iso}T12:00:00`).getDay()
      const day = s.working_hours.find((item) => item.weekday === (weekday === 0 ? 6 : weekday - 1))
      result.push({ iso, closed: !day || day.closed, label: index === 0 ? 'Сегодня' : index === 1 ? 'Завтра' : weekdayShort(iso) })
    }
    return result
  }, [s, site])

  useEffect(() => {
    if (!date) {
      const first = dates.find((item) => !item.closed)
      if (first) setDate(first.iso)
    }
  }, [dates, date])

  const { data: slots, loading: slotsLoading } = useApi<Slots>(date ? `/slots?date=${date}` : null, false)

  useEffect(() => {
    if (!slots) return
    const available = slots.slots.filter((slot) => slot.available)
    if (!available.some((slot) => slot.time === time)) {
      setTime(available[0]?.time ?? '')
    }
  }, [slots, time])

  useEffect(() => {
    if (user) {
      if (!name) setName(user.full_name)
      if (!phone) setPhone(user.phone)
    }
  }, [user, name, phone])

  const phoneMatchesAccount = Boolean(user && user.is_phone_verified && samePhone(phone, user.phone))
  const verified = phoneMatchesAccount || (samePhone(verifiedPhone, phone) && Boolean(phoneToken))

  if (!site) return null
  if (!s) return null

  if (count === 0 && !created) {
    return (
      <div className="container section">
        <EmptyState
          icon="cart"
          title="Корзина пуста"
          text="Сначала выберите товары — затем вернитесь к оформлению брони."
          action={<Link to="/catalog" className="btn btn--primary">В каталог</Link>}
        />
      </div>
    )
  }

  if (created) {
    return <OrderSuccess order={created} address={s.address} />
  }

  const submit = async () => {
    setError('')
    if (name.trim().length < 2) return setError('Укажите имя — по нему мы найдём бронь')
    if (phone.replace(/\D/g, '').length < 9) return setError('Укажите номер телефона')
    if (!verified) return setError('Подтвердите номер телефона кодом из SMS')
    if (!date || !time) return setError('Выберите дату и время получения')
    if (!consent) return setError('Необходимо согласие на обработку персональных данных')

    setSubmitting(true)
    try {
      const order = await api<Order>('/orders', {
        method: 'POST',
        body: {
          items: lines.map((line) => ({ product_id: line.productId, quantity: line.quantity })),
          pickup_date: date,
          pickup_time: time,
          customer_name: name.trim(),
          phone,
          phone_token: phoneToken || undefined,
          comment: comment.trim(),
          source: 'site',
          consent_personal_data: consent,
        },
      })
      clear()
      setCreated(order)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось оформить бронь')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="container section checkout-page">
      <div className="breadcrumbs">
        <Link to="/">Главная</Link><Icon name="chevron-right" size={13} />
        <Link to="/cart">Корзина</Link><Icon name="chevron-right" size={13} />
        <span>Оформление брони</span>
      </div>
      <div className="checkout-head">
        <div>
          <span className="eyebrow">Самовывоз · без предоплаты</span>
          <h1>Оформление брони</h1>
          <p>Выберите дату и время — соберём заказ к вашему приходу в павильоне.</p>
        </div>
        <div className="checkout-head__place">
          <Icon name="pin" size={20} />
          <div><strong>{s.city}, {s.market_name}</strong><span>{s.pavilion}</span></div>
        </div>
      </div>

      <div className="checkout-layout">
        <div className="checkout-form">
          <section className="checkout-block">
            <div className="checkout-block__head"><span className="checkout-block__num">1</span><h2>Контакты</h2></div>
            <div className="form-grid">
              <label className="field">
                <span className="field__label">Как вас зовут *</span>
                <input className="input" value={name} onChange={(event) => setName(event.target.value)} placeholder="Имя" autoComplete="name" />
              </label>
              <label className="field">
                <span className="field__label">Мобильный телефон *</span>
                <input
                  className="input"
                  value={phone}
                  onChange={(event) => {
                    const next = normalizePhoneInput(event.target.value)
                    setPhone(next)
                    setPhoneToken('')
                    setVerifiedPhone('')
                  }}
                  onBlur={() => setPhone((value) => phonePretty(value))}
                  placeholder="+375 29 123-45-67"
                  inputMode="tel"
                  autoComplete="tel"
                />
                <span className="field__hint">Нужен для подтверждения брони и связи по заказу</span>
              </label>
            </div>

            {phoneMatchesAccount ? (
              <div className="verified-account"><Icon name="check" size={18} /> Номер подтверждён в вашем аккаунте</div>
            ) : (
              <SmsVerify
                key={phone}
                phone={phone}
                purpose="order"
                onVerified={(token, verified) => {
                  setPhoneToken(token)
                  setVerifiedPhone(verified)
                }}
              />
            )}
          </section>

          <section className="checkout-block">
            <div className="checkout-block__head"><span className="checkout-block__num">2</span><h2>Дата и время получения</h2></div>
            <div className="date-strip">
              {dates.map((item) => (
                <button
                  key={item.iso}
                  type="button"
                  className={`date-chip ${date === item.iso ? 'is-active' : ''}`}
                  disabled={item.closed}
                  onClick={() => { setDate(item.iso); setTime('') }}
                >
                  <span>{item.label}</span>
                  <strong>{Number(item.iso.slice(8, 10))}</strong>
                  <small>{item.closed ? 'выходной' : humanDate(item.iso).split(' ')[1].slice(0, 3)}</small>
                </button>
              ))}
            </div>

            {slotsLoading ? (
              <div className="slots-loading"><Spinner size={18} /> Проверяем свободное время…</div>
            ) : slots && slots.is_open ? (
              <>
                <div className="slots">
                  {slots.slots.map((slot) => (
                    <button
                      key={slot.time}
                      type="button"
                      className={`slot ${time === slot.time ? 'is-active' : ''}`}
                      disabled={!slot.available}
                      onClick={() => setTime(slot.time)}
                    >
                      {slot.time}
                    </button>
                  ))}
                </div>
                {slots.message && <p className="field__hint">{slots.message}</p>}
              </>
            ) : (
              <div className="notice notice--warn"><Icon name="alert" size={18} /><span>{slots?.message ?? 'Выберите другую дату'}</span></div>
            )}

            <div className="pickup-hint">
              <Icon name="clock" size={18} />
              <span>Заказ хранится 2 часа после выбранного времени. При опоздании позвоните — постараемся сохранить бронь.</span>
            </div>
          </section>

          <section className="checkout-block">
            <div className="checkout-block__head"><span className="checkout-block__num">3</span><h2>Комментарий</h2></div>
            <label className="field">
              <span className="field__label">Пожелания к заказу</span>
              <textarea
                className="textarea"
                rows={3}
                value={comment}
                onChange={(event) => setComment(event.target.value.slice(0, 600))}
                placeholder="Например: почистить, разделать на порции, упаковать отдельно"
              />
              <span className="field__hint">{comment.length}/600</span>
            </label>

            <label className="checkbox">
              <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
              <span>
                Согласен(-на) на обработку персональных данных и принимаю{' '}
                <Link to="/legal/privacy" target="_blank">политику</Link> и{' '}
                <Link to="/legal/offer" target="_blank">правила бронирования</Link>. Мне понятно, что доставка не осуществляется.
              </span>
            </label>
          </section>

          {error && <div className="notice notice--error"><Icon name="alert" size={18} /><span>{error}</span></div>}
        </div>

        <aside className="checkout-summary">
          <h2>Ваш заказ</h2>
          <div className="checkout-summary__items">
            {lines.map((line) => (
              <div className="checkout-line" key={line.productId}>
                <div className="checkout-line__img">
                  {line.image_url ? <img src={assetUrl(line.image_url)} alt="" /> : <Icon name="fish" size={22} />}
                </div>
                <div className="checkout-line__info">
                  <strong>{line.title}</strong>
                  <span>{formatQty(line.quantity)} {unitShort(line.unit)} × {formatMoney(line.price)}</span>
                </div>
                <b>{formatMoney(line.price * line.quantity)}</b>
              </div>
            ))}
          </div>
          <dl className="checkout-summary__totals">
            <div><dt>Товаров</dt><dd>{count}</dd></div>
            <div><dt>Сумма</dt><dd>{formatMoney(subtotal)}</dd></div>
            <div><dt>Доставка</dt><dd>самовывоз</dd></div>
          </dl>
          <div className="checkout-summary__total">
            <span>К оплате при получении</span>
            <strong>{formatMoney(subtotal)}</strong>
          </div>
          <button type="button" className="btn btn--primary btn--lg btn--block" onClick={submit} disabled={submitting}>
            {submitting ? <Spinner size={18} /> : <Icon name="check" size={18} />}
            {submitting ? 'Отправляем…' : 'Отправить бронь'}
          </button>
          <p className="checkout-summary__note">
            Нажимая кнопку, вы подтверждаете состав заказа. Мы позвоним или напишем, если позиция закончится.
          </p>
          <div className="checkout-summary__contact">
            <Icon name="phone" size={17} />
            <span>Вопросы: <a href={`tel:${s.phone.replace(/[^\d+]/g, '')}`}>{s.phone}</a></span>
          </div>
        </aside>
      </div>
    </div>
  )
}

function OrderSuccess({ order, address }: { order: Order; address: string }) {
  return (
    <div className="container section">
      <div className="order-success">
        <span className="order-success__icon"><Icon name="check" size={40} /></span>
        <span className="eyebrow">Бронь оформлена</span>
        <h1>Спасибо! Заказ принят</h1>
        <p className="order-success__lead">
          Мы отправили SMS с номером брони. Соберём заказ к выбранному времени — оплата в павильоне.
        </p>

        <div className="order-success__card">
          <div className="order-success__number">
            <span>Номер брони</span>
            <strong>{order.number}</strong>
          </div>
          <div className="order-success__grid">
            <div><span>Получение</span><strong>{humanDate(order.pickup_date)}, {order.pickup_time}</strong></div>
            <div><span>Сумма</span><strong>{formatMoney(order.total_amount)}</strong></div>
            <div><span>Позиций</span><strong>{order.items_count}</strong></div>
            <div><span>Телефон</span><strong>{order.phone_formatted}</strong></div>
          </div>
          <div className="order-success__address"><Icon name="pin" size={18} /><span>{address}</span></div>
          <ul className="order-success__items">
            {order.items.map((item) => (
              <li key={item.id}>
                <span>{item.title}</span>
                <b>{formatQty(item.quantity)} {unitShort(item.unit)}</b>
              </li>
            ))}
          </ul>
        </div>

        <div className="order-success__steps">
          <div><span>1</span><p>Мы проверим наличие и соберём заказ.</p></div>
          <div><span>2</span><p>Придём SMS или позвоним, если что-то изменится.</p></div>
          <div><span>3</span><p>Приходите в павильон к выбранному времени и назовите номер брони.</p></div>
        </div>

        <div className="order-success__actions">
          {order.user_id ? (
            <Link to="/account" className="btn btn--primary">Мои брони <Icon name="arrow-right" size={17} /></Link>
          ) : (
            <Link to="/lookup" className="btn btn--primary">Найти бронь <Icon name="arrow-right" size={17} /></Link>
          )}
          <Link to="/catalog" className="btn btn--outline">Вернуться в каталог</Link>
        </div>
        <p className="order-success__note">
          Сохраните номер брони. Найти заказ можно по номеру и телефону на странице «Найти бронь».
        </p>
      </div>
    </div>
  )
}
