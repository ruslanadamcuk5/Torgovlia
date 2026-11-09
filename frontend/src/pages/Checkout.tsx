import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useSite } from '../store/SettingsContext'
import { useCart } from '../store/CartContext'
import { syncCart } from '../lib/cartSession'
import { useAuth } from '../store/AuthContext'
import { useToast } from '../store/ToastContext'
import { useApi } from '../lib/useApi'
import { api, assetUrl } from '../lib/api'
import { SmsVerify } from '../components/SmsVerify'
import { Spinner, EmptyState } from '../components/ui'
import { Icon } from '../components/icons'
import type { DeliveryZone, Order, PromoValidation, Slots } from '../lib/types'
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
  const [fulfillment, setFulfillment] = useState<'pickup' | 'delivery'>('pickup')
  const [zoneId, setZoneId] = useState('')
  const [address, setAddress] = useState('')
  const [promoInput, setPromoInput] = useState('')
  const [promo, setPromo] = useState<PromoValidation | null>(null)
  const [promoError, setPromoError] = useState('')
  const [promoBusy, setPromoBusy] = useState(false)
  const [usePoints, setUsePoints] = useState(false)
  const [certificateInput, setCertificateInput] = useState('')
  const [certificate, setCertificate] = useState<{ code: string; balance: number; status_label: string } | null>(null)
  const [certificateError, setCertificateError] = useState('')
  const [certificateBusy, setCertificateBusy] = useState(false)
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
  const deliveryAvailable = Boolean(site?.features?.delivery)
  const { data: zones } = useApi<DeliveryZone[]>(deliveryAvailable ? '/delivery/zones' : null, false)
  const loyaltyAvailable = Boolean(site?.features?.loyalty)
  const { data: loyalty } = useApi<{
    enabled: boolean
    balance: number
    level_info: { title: string }
    settings: { point_value: number; max_redeem_percent: number; min_redeem_points: number }
  }>(loyaltyAvailable && user ? '/account/loyalty' : null, false)

  const afterPromo = promo ? promo.total : subtotal
  const maxRedeemPoints = loyalty?.enabled
    ? Math.min(
        loyalty.balance,
        Math.floor((afterPromo * loyalty.settings.max_redeem_percent) / 100 / loyalty.settings.point_value),
      )
    : 0
  const canRedeem = Boolean(loyalty?.enabled && maxRedeemPoints >= loyalty.settings.min_redeem_points)
  const pointsToUse = usePoints && canRedeem ? maxRedeemPoints : 0
  const pointsDiscount = pointsToUse * (loyalty?.settings.point_value ?? 0)

  useEffect(() => {
    if (fulfillment === 'delivery' && zones?.length && !zoneId) {
      setZoneId(String(zones[0].id))
    }
  }, [fulfillment, zones, zoneId])

  useEffect(() => {
    if (!deliveryAvailable) setFulfillment('pickup')
  }, [deliveryAvailable])

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
          text="Сначала выберите товары — затем вернитесь к оформлению заказа."
          action={<Link to="/catalog" className="btn btn--primary">В каталог</Link>}
        />
      </div>
    )
  }

  if (created) {
    return (
      <OrderSuccess
        order={created}
        address={created.fulfillment === 'delivery' ? created.delivery_address ?? '' : s.address}
      />
    )
  }

  const selectedZone = zones?.find((zone) => String(zone.id) === zoneId) ?? null
  const deliveryFee = fulfillment === 'delivery' && selectedZone
    ? (selectedZone.free_from > 0 && subtotal >= selectedZone.free_from ? 0 : selectedZone.fee)
    : 0

  const submit = async () => {
    setError('')
    if (name.trim().length < 2) return setError('Укажите имя — по нему мы найдём заказ')
    if (phone.replace(/\D/g, '').length < 9) return setError('Укажите номер телефона')
    if (!verified) return setError('Подтвердите номер телефона кодом из SMS')
    if (!date || !time) return setError('Выберите дату и время получения')
    if (fulfillment === 'delivery') {
      if (!zoneId) return setError('Выберите зону доставки')
      if (address.trim().length < 5) return setError('Укажите адрес доставки: улица, дом, квартира')
    }
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
          promo_code: promo?.code || '',
          gift_certificate_code: certificate?.code || '',
          fulfillment,
          delivery_zone_id: fulfillment === 'delivery' ? Number(zoneId) : undefined,
          delivery_address: fulfillment === 'delivery' ? address.trim() : '',
          source: 'site',
          points_used: pointsToUse,
          consent_personal_data: consent,
        },
      })
      clear()
      setCreated(order)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось оформить заказ')
    } finally {
      setSubmitting(false)
    }
  }

  const applyPromo = async () => {
    const code = promoInput.trim()
    if (!code) return
    setPromoBusy(true)
    setPromoError('')
    try {
      const result = await api<PromoValidation>('/promo-codes/validate', {
        method: 'POST',
        body: { code, subtotal },
        auth: false,
      })
      setPromo(result)
      toast(`Промокод применён: −${formatMoney(result.discount)}`)
    } catch (err) {
      setPromo(null)
      setPromoError(err instanceof Error ? err.message : 'Промокод не подошёл')
    } finally {
      setPromoBusy(false)
    }
  }

  const applyCertificate = async () => {
    const code = certificateInput.trim().toUpperCase()
    if (!code) return
    setCertificateBusy(true)
    setCertificateError('')
    try {
      const result = await api<{ code: string; balance: number; amount: number; status_label: string }>(
        '/gift-certificates/check',
        {
          method: 'POST',
          body: {
            code,
            subtotal: Math.max(0, afterPromo - pointsDiscount) + (fulfillment === 'delivery' ? deliveryFee : 0),
          },
          auth: false,
        },
      )
      setCertificate({ code: result.code, balance: result.balance, status_label: result.status_label })
      toast(`Сертификат применён: доступно ${formatMoney(result.balance)}`)
    } catch (err) {
      setCertificate(null)
      setCertificateError(err instanceof Error ? err.message : 'Сертификат не подошёл')
    } finally {
      setCertificateBusy(false)
    }
  }

  const totalBeforeGift = Math.max(0, afterPromo - pointsDiscount) + (fulfillment === 'delivery' ? deliveryFee : 0)
  const giftApplied = certificate ? Math.min(certificate.balance, totalBeforeGift) : 0
  const amountDue = Math.max(0, totalBeforeGift - giftApplied)

  return (
    <div className="container section checkout-page">
      <div className="breadcrumbs">
        <Link to="/">Главная</Link><Icon name="chevron-right" size={13} />
        <Link to="/cart">Корзина</Link><Icon name="chevron-right" size={13} />
        <span>Оформление заказа</span>
      </div>
      <div className="checkout-head">
        <div>
          <span className="eyebrow">{deliveryAvailable ? 'Самовывоз или доставка · без предоплаты' : 'Самовывоз · без предоплаты'}</span>
          <h1>Оформление заказа</h1>
          <p>
            {deliveryAvailable
              ? 'Выберите способ получения и удобное время — оплата при получении.'
              : 'Выберите дату и время — соберём заказ к вашему приходу в магазине.'}
          </p>
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
                <span className="field__hint">Нужен для подтверждения заказа и связи с вами</span>
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
                  void syncCart(lines, { name, phone }).catch(() => undefined)
                }}
              />
            )}
          </section>

          {deliveryAvailable && (
            <section className="checkout-block">
              <div className="checkout-block__head"><span className="checkout-block__num">2</span><h2>Способ получения</h2></div>
              <div className="fulfillment-choice">
                <button
                  type="button"
                  className={fulfillment === 'pickup' ? 'is-active' : ''}
                  onClick={() => setFulfillment('pickup')}
                >
                  <Icon name="pin" size={22} />
                  <span>
                    <strong>Самовывоз</strong>
                    <small>{s.city}, {s.market_name} · {s.pavilion}</small>
                  </span>
                  <b>Бесплатно</b>
                </button>
                <button
                  type="button"
                  className={fulfillment === 'delivery' ? 'is-active' : ''}
                  onClick={() => setFulfillment('delivery')}
                >
                  <Icon name="car" size={22} />
                  <span>
                    <strong>Доставка</strong>
                    <small>{selectedZone?.eta || 'по городу и району'}</small>
                  </span>
                  <b>{deliveryFee ? formatMoney(deliveryFee) : 'бесплатно'}</b>
                </button>
              </div>

              {fulfillment === 'delivery' && (
                <div className="fulfillment-fields">
                  <label className="field">
                    <span className="field__label">Зона доставки *</span>
                    <select className="input input--select" value={zoneId} onChange={(event) => setZoneId(event.target.value)}>
                      {(zones ?? []).map((zone) => (
                        <option key={zone.id} value={zone.id}>{zone.name} — {formatMoney(zone.fee)}</option>
                      ))}
                    </select>
                    {selectedZone && (
                      <span className="field__hint">
                        {selectedZone.areas}
                        {selectedZone.free_from > 0 && ` · бесплатно от ${formatMoney(selectedZone.free_from)}`}
                        {selectedZone.min_order > 0 && ` · минимальный заказ ${formatMoney(selectedZone.min_order)}`}
                      </span>
                    )}
                  </label>
                  <label className="field">
                    <span className="field__label">Адрес доставки *</span>
                    <textarea
                      className="textarea"
                      rows={2}
                      value={address}
                      onChange={(event) => setAddress(event.target.value)}
                      placeholder="Город, улица, дом, квартира, подъезд"
                      maxLength={600}
                    />
                  </label>
                </div>
              )}
            </section>
          )}

          <section className="checkout-block">
            <div className="checkout-block__head"><span className="checkout-block__num">{deliveryAvailable ? 3 : 2}</span><h2>{fulfillment === 'delivery' ? 'Дата и время доставки' : 'Дата и время получения'}</h2></div>
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
              <span>Заказ хранится 2 часа после выбранного времени. При опоздании позвоните — постараемся сохранить заказ.</span>
            </div>
          </section>

          <section className="checkout-block">
            <div className="checkout-block__head"><span className="checkout-block__num">{deliveryAvailable ? 4 : 3}</span><h2>Комментарий</h2></div>
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
                <Link to="/legal/offer" target="_blank">правила оформления заказов</Link>. Мне понятно, что доставка не осуществляется.
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
                  {line.image_url ? <img src={assetUrl(line.image_url)} alt="" /> : <Icon name="image" size={22} />}
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
            {promo && (
              <div className="checkout-summary__discount">
                <dt>Промокод {promo.code}</dt>
                <dd>−{formatMoney(promo.discount)}</dd>
              </div>
            )}
            {pointsToUse > 0 && (
              <div className="checkout-summary__discount">
                <dt>Баллы · {pointsToUse}</dt>
                <dd>−{formatMoney(pointsDiscount)}</dd>
              </div>
            )}
            {certificate && giftApplied > 0 && (
              <div className="checkout-summary__discount">
                <dt>Сертификат {certificate.code}</dt>
                <dd>−{formatMoney(giftApplied)}</dd>
              </div>
            )}
            <div>
              <dt>Получение</dt>
              <dd>{fulfillment === 'delivery' ? selectedZone?.name ?? 'доставка' : 'самовывоз'}</dd>
            </div>
            {fulfillment === 'delivery' && (
              <div>
                <dt>Стоимость доставки</dt>
                <dd>{deliveryFee ? formatMoney(deliveryFee) : 'бесплатно'}</dd>
              </div>
            )}
          </dl>

          {site.features?.promo_codes && (
            <div className="promo-apply">
              <span className="promo-apply__label">Промокод</span>
              <div className="promo-apply__row">
                <input
                  className="input input--sm"
                  value={promoInput}
                  onChange={(event) => {
                    setPromoInput(event.target.value.toUpperCase())
                    setPromo(null)
                    setPromoError('')
                  }}
                  placeholder="Например, ВЕСНА10"
                  aria-label="Промокод"
                />
                <button
                  type="button"
                  className="btn btn--outline btn--sm"
                  onClick={applyPromo}
                  disabled={promoBusy || !promoInput.trim()}
                >
                  {promoBusy ? <Spinner size={15} /> : 'Применить'}
                </button>
              </div>
              {promoError && <span className="promo-apply__error">{promoError}</span>}
              {promo && !promoError && (
                <span className="promo-apply__ok">
                  <Icon name="check" size={14} /> Скидка применена
                  {promo.note ? ` · ${promo.note}` : ''}
                </span>
              )}
            </div>
          )}

          {site.features?.gift_certificates && (
            <div className="promo-apply">
              <span className="promo-apply__label">Подарочный сертификат</span>
              <div className="promo-apply__row">
                <input
                  className="input input--sm"
                  value={certificateInput}
                  onChange={(event) => {
                    setCertificateInput(event.target.value.toUpperCase())
                    setCertificate(null)
                    setCertificateError('')
                  }}
                  placeholder="GIFT-XXXX-XXXX"
                  aria-label="Подарочный сертификат"
                />
                <button
                  type="button"
                  className="btn btn--outline btn--sm"
                  onClick={() => void applyCertificate()}
                  disabled={certificateBusy || !certificateInput.trim()}
                >
                  {certificateBusy ? <Spinner size={15} /> : 'Применить'}
                </button>
              </div>
              {certificateError && <span className="promo-apply__error">{certificateError}</span>}
              {certificate && !certificateError && (
                <span className="promo-apply__ok">
                  <Icon name="check" size={14} /> {certificate.status_label} · доступно {formatMoney(certificate.balance)}
                  {certificate.balance > totalBeforeGift && giftApplied > 0 ? ` · спишется ${formatMoney(giftApplied)}` : ''}
                </span>
              )}
              <p className="promo-apply__hint">
                <Link to="/gift">Где взять сертификат</Link>
              </p>
            </div>
          )}

          {canRedeem && loyalty && (
            <label className="loyalty-redeem">
              <input
                type="checkbox"
                checked={usePoints}
                onChange={(event) => setUsePoints(event.target.checked)}
              />
              <span>
                <strong>Списать {maxRedeemPoints} баллов</strong>
                <small>
                  −{formatMoney(maxRedeemPoints * loyalty.settings.point_value)} · уровень «
                  {loyalty.level_info.title}» · останется {loyalty.balance - maxRedeemPoints}
                </small>
              </span>
            </label>
          )}

          <div className="checkout-summary__total">
            <span>{amountDue > 0 ? 'К оплате при получении' : 'Сертификат покрывает заказ'}</span>
            <strong>{formatMoney(amountDue)}</strong>
          </div>
          <button type="button" className="btn btn--primary btn--lg btn--block" onClick={submit} disabled={submitting}>
            {submitting ? <Spinner size={18} /> : <Icon name="check" size={18} />}
            {submitting ? 'Отправляем…' : 'Отправить заказ'}
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
        <span className="eyebrow">Заказ оформлен</span>
        <h1>Спасибо! Заказ принят</h1>
        <p className="order-success__lead">
          {order.fulfillment === 'delivery'
            ? 'Мы отправили SMS с номером заказа. Соберём заказ и привезём к выбранному времени — оплата при получении.'
            : 'Мы отправили SMS с номером заказа. Соберём заказ к выбранному времени — оплата в магазине.'}
        </p>

        <div className="order-success__card">
          <div className="order-success__number">
            <span>Номер заказа</span>
            <strong>{order.number}</strong>
          </div>
          <div className="order-success__grid">
            <div>
              <span>{order.fulfillment === 'delivery' ? 'Доставка' : 'Получение'}</span>
              <strong>{humanDate(order.pickup_date)}, {order.pickup_time}</strong>
            </div>
            <div><span>Сумма</span><strong>{formatMoney(order.total_amount)}</strong></div>
            {Boolean(order.delivery_fee) && (
              <div><span>Доставка{order.delivery_zone_name ? ` · ${order.delivery_zone_name}` : ''}</span><strong>{formatMoney(order.delivery_fee ?? 0)}</strong></div>
            )}
            {Boolean(order.discount_amount) && (
              <div><span>Скидка {order.promo_code}</span><strong>−{formatMoney(order.discount_amount ?? 0)}</strong></div>
            )}
            {Boolean(order.points_discount) && (
              <div><span>Баллы · {order.points_used ?? 0}</span><strong>−{formatMoney(order.points_discount ?? 0)}</strong></div>
            )}
            {Boolean(order.gift_certificate_amount) && (
              <div><span>Сертификат {order.gift_certificate_code}</span><strong>−{formatMoney(order.gift_certificate_amount ?? 0)}</strong></div>
            )}
            {Boolean(order.points_earned) && (
              <div><span>Начислим баллов</span><strong>+{order.points_earned}</strong></div>
            )}
            <div><span>Позиций</span><strong>{order.items_count}</strong></div>
            <div><span>Телефон</span><strong>{order.phone_formatted}</strong></div>
          </div>
          <div className="order-success__address">
            <Icon name={order.fulfillment === 'delivery' ? 'car' : 'pin'} size={18} />
            <span>{address}</span>
          </div>
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
          <div>
            <span>3</span>
            <p>
              {order.fulfillment === 'delivery'
                ? 'Курьер привезёт заказ к выбранному времени. Назовите номер заказа и оплатите при получении.'
                : 'Приходите в магазин к выбранному времени и назовите номер заказа.'}
            </p>
          </div>
        </div>

        <div className="order-success__actions">
          {order.user_id ? (
            <Link to="/account" className="btn btn--primary">Мои заказы <Icon name="arrow-right" size={17} /></Link>
          ) : (
            <Link to="/lookup" className="btn btn--primary">Найти заказ <Icon name="arrow-right" size={17} /></Link>
          )}
          <Link to="/catalog" className="btn btn--outline">Вернуться в каталог</Link>
        </div>
        <p className="order-success__note">
          Сохраните номер заказа. Найти заказ можно по номеру и телефону на странице «Найти заказ».
        </p>
      </div>
    </div>
  )
}
