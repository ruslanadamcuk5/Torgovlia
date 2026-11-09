import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../store/AuthContext'
import { useSite } from '../store/SettingsContext'
import { useToast } from '../store/ToastContext'
import { api } from '../lib/api'
import { useApi } from '../lib/useApi'
import { Icon } from '../components/icons'
import { EmptyState, Loader } from '../components/ui'
import { formatMoney, humanDate } from '../lib/format'
import type { DeliveryZone, Product, Subscription } from '../lib/types'

const INTERVALS = [
  { value: 7, label: 'Каждую неделю', hint: 'продукты, вода, корм' },
  { value: 14, label: 'Раз в две недели', hint: 'самое популярное' },
  { value: 30, label: 'Раз в месяц', hint: 'большие закупки' },
]

const plusDays = (days: number) => {
  const date = new Date()
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

type Picked = { product_id: number; quantity: number }

export default function Subscriptions() {
  const { site } = useSite()
  const { user } = useAuth()
  const { toast } = useToast()
  const enabled = site?.features?.subscriptions === true
  const delivery = site?.features?.delivery === true

  const products = useApi<{ items: Product[] }>(enabled ? '/products?available_only=true' : null, false)
  const zones = useApi<DeliveryZone[]>(enabled && delivery && user ? '/delivery/zones' : null, false)
  const mine = useApi<{ items: Subscription[] }>(
    enabled && user ? '/account/subscriptions' : null,
  )

  const [query, setQuery] = useState('')
  const [picked, setPicked] = useState<Picked[]>([])
  const [form, setForm] = useState({
    interval_days: 14,
    next_order_date: plusDays(2),
    fulfillment: 'pickup' as 'pickup' | 'delivery',
    delivery_zone_id: '',
    delivery_address: '',
    comment: '',
  })
  const [busy, setBusy] = useState(false)

  const productMap = useMemo(
    () => new Map((products.data?.items ?? []).map((product) => [product.id, product])),
    [products.data],
  )

  const available = useMemo(() => {
    const term = query.trim().toLowerCase()
    const list = (products.data?.items ?? []).filter((product) => product.can_order)
    return (term ? list.filter((product) => product.title.toLowerCase().includes(term)) : list).slice(0, 18)
  }, [products.data, query])

  const pickedTotal = picked.reduce(
    (sum, item) => sum + (productMap.get(item.product_id)?.final_price ?? 0) * item.quantity,
    0,
  )

  const addProduct = (product: Product) => {
    setPicked((current) => {
      const existing = current.find((item) => item.product_id === product.id)
      if (existing) {
        return current.map((item) =>
          item.product_id === product.id ? { ...item, quantity: item.quantity + 1 } : item,
        )
      }
      return [...current, { product_id: product.id, quantity: 1 }]
    })
  }

  const setQuantity = (productId: number, value: number) => {
    setPicked((current) =>
      current.map((item) =>
        item.product_id === productId
          ? { ...item, quantity: Math.max(0.1, Number.isFinite(value) ? value : 1) }
          : item,
      ),
    )
  }

  if (!site) return null
  const s = site.settings

  if (!enabled) {
    return (
      <div className="container section">
        <div className="empty-state">
          <div className="empty-state__icon"><Icon name="refresh" size={28} /></div>
          <h3>Регулярные заказы пока не подключены</h3>
          <p>Сервис можно включить в админке магазина в разделе «Сервисы».</p>
          <Link to="/catalog" className="btn btn--primary">В каталог</Link>
        </div>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="container section">
        <div className="subs-login panel">
          <span className="empty-state__icon"><Icon name="refresh" size={28} /></span>
          <h1>Регулярные заказы</h1>
          <p>
            Соберите корзину один раз — магазин будет собирать её к выбранной дате.
            Подписка управляется в личном кабинете: пауза, возобновление и отмена.
          </p>
          <div className="subs-login__actions">
            <Link to="/login" className="btn btn--primary">Войти</Link>
            <Link to="/register" className="btn btn--outline">Зарегистрироваться</Link>
          </div>
          <ul>
            <li>Интервал: неделя, две недели или месяц</li>
            <li>Любой состав — как в обычной корзине</li>
            <li>Самовывоз или доставка</li>
          </ul>
        </div>
      </div>
    )
  }

  const submit = async () => {
    if (!picked.length) return toast('Добавьте хотя бы один товар', 'error')
    if (form.fulfillment === 'delivery' && form.delivery_address.trim().length < 5) {
      return toast('Укажите адрес доставки', 'error')
    }
    setBusy(true)
    try {
      await api('/account/subscriptions', {
        method: 'POST',
        body: {
          interval_days: form.interval_days,
          next_order_date: form.next_order_date,
          items: picked,
          fulfillment: form.fulfillment,
          delivery_zone_id: form.delivery_zone_id ? Number(form.delivery_zone_id) : null,
          delivery_address: form.delivery_address.trim(),
          comment: form.comment.trim(),
        },
      })
      toast('Регулярный заказ создан')
      setPicked([])
      setForm({ ...form, comment: '', delivery_address: '' })
      mine.reload()
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось создать подписку', 'error')
    } finally {
      setBusy(false)
    }
  }

  const changeStatus = async (sub: Subscription, status: 'active' | 'paused' | 'cancelled') => {
    setBusy(true)
    try {
      await api(`/account/subscriptions/${sub.id}`, { method: 'PATCH', body: { status } })
      toast(
        status === 'paused'
          ? 'Подписка на паузе'
          : status === 'active'
            ? 'Подписка возобновлена'
            : 'Подписка отменена',
      )
      mine.reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось обновить подписку', 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="subs-public">
      <section className="subs-hero">
        <div className="container subs-hero__inner">
          <div>
            <span className="eyebrow">Один раз собрали — дальше по расписанию</span>
            <h1>Регулярные заказы</h1>
            <p>
              Подходит для товаров, которые покупают постоянно. Мы создадим заказ
              автоматически в ближайшее свободное окно, а вы сможете поставить
              подписку на паузу в любой момент.
            </p>
          </div>
          <div className="subs-hero__points">
            <span><Icon name="check" size={15} /> Неделя, две недели или месяц</span>
            <span><Icon name="check" size={15} /> Любой состав корзины</span>
            <span><Icon name="check" size={15} /> Управление в кабинете</span>
          </div>
        </div>
      </section>

      <div className="container section subs-public__grid">
        <section className="panel subs-public__form">
          <div className="panel__head">
            <div>
              <h2>Новая подписка</h2>
              <p className="muted">Первый заказ — {humanDate(form.next_order_date)}. Дальше по выбранному интервалу.</p>
            </div>
          </div>

          <div className="subs-intervals">
            {INTERVALS.map((item) => (
              <button
                key={item.value}
                type="button"
                className={form.interval_days === item.value ? 'is-active' : ''}
                onClick={() => setForm({ ...form, interval_days: item.value })}
              >
                <strong>{item.label}</strong>
                <small>{item.hint}</small>
              </button>
            ))}
          </div>

          <div className="subs-form__row">
            <label className="field">
              <span className="field__label">Первый заказ</span>
              <input className="input" type="date" min={plusDays(0)} value={form.next_order_date} onChange={(event) => setForm({ ...form, next_order_date: event.target.value })} />
            </label>
            <label className="field">
              <span className="field__label">Получение</span>
              <select className="input" value={form.fulfillment} onChange={(event) => setForm({ ...form, fulfillment: event.target.value as 'pickup' | 'delivery' })}>
                <option value="pickup">Самовывоз</option>
                {delivery && <option value="delivery">Доставка</option>}
              </select>
            </label>
          </div>

          {form.fulfillment === 'delivery' && (
            <div className="subs-form__row">
              <label className="field">
                <span className="field__label">Зона доставки</span>
                <select className="input" value={form.delivery_zone_id} onChange={(event) => setForm({ ...form, delivery_zone_id: event.target.value })}>
                  <option value="">Выберите зону</option>
                  {(zones.data ?? []).map((zone) => (
                    <option key={zone.id} value={zone.id}>{zone.name} · {formatMoney(zone.fee)}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span className="field__label">Адрес</span>
                <input className="input" value={form.delivery_address} onChange={(event) => setForm({ ...form, delivery_address: event.target.value })} placeholder="Улица, дом, квартира" />
              </label>
            </div>
          )}

          <label className="field">
            <span className="field__label">Комментарий</span>
            <input className="input" value={form.comment} onChange={(event) => setForm({ ...form, comment: event.target.value })} placeholder="Например: звонить за час" maxLength={600} />
          </label>

          <div className="subs-picker">
            <div className="subs-picker__head">
              <strong>Что повторять</strong>
              <span>{picked.length ? `${picked.length} поз. · ${formatMoney(pickedTotal)}` : 'корзина пуста'}</span>
            </div>
            <input
              className="input"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Найти товар"
            />
            <div className="subs-picker__list">
              {available.map((product) => (
                <button type="button" key={product.id} onClick={() => addProduct(product)}>
                  <span>{product.title}</span>
                  <small>{formatMoney(product.final_price)}</small>
                  <Icon name="plus" size={14} />
                </button>
              ))}
              {!available.length && <p className="muted">Ничего не найдено</p>}
            </div>
          </div>

          {picked.length > 0 && (
            <div className="subs-picked">
              {picked.map((item) => {
                const product = productMap.get(item.product_id)
                return (
                  <div key={item.product_id}>
                    <span>{product?.title ?? 'Товар'}</span>
                    <input
                      className="input"
                      type="number"
                      min={0.1}
                      step={product?.unit === 'kg' ? 0.1 : 1}
                      value={item.quantity}
                      onChange={(event) => setQuantity(item.product_id, Number(event.target.value))}
                    />
                    <button
                      type="button"
                      onClick={() => setPicked((current) => current.filter((row) => row.product_id !== item.product_id))}
                      aria-label="Убрать"
                    >
                      <Icon name="trash" size={14} />
                    </button>
                  </div>
                )
              })}
            </div>
          )}

          <button type="button" className="btn btn--primary btn--lg btn--block" disabled={busy} onClick={() => void submit()}>
            <Icon name="refresh" size={18} /> {busy ? 'Создаём…' : 'Оформить регулярный заказ'}
          </button>
          <p className="subs-form__hint">
            Оплата — при получении. Сумма пересчитывается по актуальным ценам перед каждым заказом.
          </p>
        </section>

        <aside className="subs-public__side">
          <section className="panel subs-my">
            <div className="panel__head">
              <div>
                <h2>Мои подписки</h2>
                <p className="muted">Пауза, возобновление и отмена.</p>
              </div>
            </div>
            {mine.loading ? (
              <Loader label="Загружаем" />
            ) : mine.data?.items.length ? (
              <div className="subs-my__list">
                {mine.data.items.map((sub) => (
                  <article key={sub.id} className={`subs-my__card is-${sub.status}`}>
                    <div className="subs-my__head">
                      <strong>{sub.interval_label}</strong>
                      <span className={`badge badge--${sub.status === 'active' ? 'fresh' : sub.status === 'paused' ? 'gold' : 'muted'}`}>
                        {sub.status_label}
                      </span>
                    </div>
                    <p>
                      {sub.status === 'active'
                        ? `Следующий заказ ${sub.next_order_date ? humanDate(sub.next_order_date) : '—'}`
                        : sub.status === 'paused'
                          ? 'Подписка приостановлена'
                          : 'Подписка отменена'}
                    </p>
                    <div className="subs-my__items">
                      {sub.items.map((item) => <span key={item.id}>{item.title} × {item.quantity}</span>)}
                    </div>
                    <div className="subs-my__actions">
                      {sub.status === 'active' && (
                        <button type="button" className="btn btn--sm btn--outline" disabled={busy} onClick={() => void changeStatus(sub, 'paused')}>
                          Пауза
                        </button>
                      )}
                      {sub.status === 'paused' && (
                        <button type="button" className="btn btn--sm btn--primary" disabled={busy} onClick={() => void changeStatus(sub, 'active')}>
                          Возобновить
                        </button>
                      )}
                      {sub.status !== 'cancelled' && (
                        <button type="button" className="btn btn--sm btn--ghost" disabled={busy} onClick={() => void changeStatus(sub, 'cancelled')}>
                          Отменить
                        </button>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState icon="refresh" title="Пока нет подписок" text="Соберите первый регулярный заказ в форме." />
            )}
          </section>

          <section className="panel subs-rules">
            <h2>Как это работает</h2>
            <ol>
              <li>Выбираете товары и интервал.</li>
              <li>Магазин создаёт заказ в ближайшее свободное окно.</li>
              <li>За день до заказа можно поставить подписку на паузу.</li>
              <li>Оплата и получение — как у обычного заказа.</li>
            </ol>
            <p>Вопросы — по телефону <a href={`tel:${s.phone.replace(/[^\d+]/g, '')}`}>{s.phone}</a>.</p>
          </section>
        </aside>
      </div>
    </div>
  )
}
