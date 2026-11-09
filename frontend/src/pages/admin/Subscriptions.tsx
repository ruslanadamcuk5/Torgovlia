import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Icon } from '../../components/icons'
import { EmptyState, Loader } from '../../components/ui'
import { formatMoney, humanDate } from '../../lib/format'
import type { Product, Subscription, SubscriptionListResponse } from '../../lib/types'

const FILTERS = [
  { code: 'all', title: 'Все' },
  { code: 'active', title: 'Активные' },
  { code: 'paused', title: 'На паузе' },
  { code: 'cancelled', title: 'Отменённые' },
] as const

const INTERVALS = [
  { value: 7, label: 'Раз в неделю' },
  { value: 14, label: 'Раз в две недели' },
  { value: 30, label: 'Раз в месяц' },
]

const STATUS_TONE: Record<string, string> = {
  active: 'fresh',
  paused: 'gold',
  cancelled: 'muted',
}

const tomorrow = () => {
  const date = new Date()
  date.setDate(date.getDate() + 1)
  return date.toISOString().slice(0, 10)
}

type Picked = { product_id: number; quantity: number }

export default function Subscriptions() {
  const { toast } = useToast()
  const features = useApi<{ services: Record<string, boolean> }>('/admin/services/features')
  const enabled = features.data?.services.subscriptions === true
  const { data, loading, error, reload } = useApi<SubscriptionListResponse>(
    enabled ? '/admin/subscriptions' : null,
  )
  const products = useApi<{ items: Product[]; total: number }>(
    enabled ? '/admin/products?limit=500&include_inactive=false' : null,
  )

  const [filter, setFilter] = useState<string>('all')
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState(false)
  const [productQuery, setProductQuery] = useState('')
  const [picked, setPicked] = useState<Picked[]>([])
  const [form, setForm] = useState({
    customer_name: '',
    phone: '',
    interval_days: 14,
    next_order_date: tomorrow(),
    fulfillment: 'pickup' as 'pickup' | 'delivery',
    delivery_address: '',
    comment: '',
  })

  const items = data?.items ?? []
  const summary = data?.summary
  const productMap = useMemo(
    () => new Map((products.data?.items ?? []).map((product) => [product.id, product])),
    [products.data],
  )

  const visible = useMemo(() => {
    const term = query.trim().toLowerCase()
    return items.filter((sub) => {
      if (filter !== 'all' && sub.status !== filter) return false
      if (!term) return true
      return `${sub.customer_name} ${sub.phone} ${sub.items.map((item) => item.title).join(' ')}`
        .toLowerCase()
        .includes(term)
    })
  }, [items, filter, query])

  const available = useMemo(() => {
    const term = productQuery.trim().toLowerCase()
    const list = products.data?.items ?? []
    return (term ? list.filter((product) => product.title.toLowerCase().includes(term)) : list).slice(0, 24)
  }, [products.data, productQuery])

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

  const removeProduct = (productId: number) => {
    setPicked((current) => current.filter((item) => item.product_id !== productId))
  }

  const pickedTotal = picked.reduce((sum, item) => {
    const product = productMap.get(item.product_id)
    return sum + (product ? product.final_price * item.quantity : 0)
  }, 0)

  const create = async () => {
    if (form.customer_name.trim().length < 2) return toast('Укажите имя покупателя', 'error')
    if (form.phone.replace(/\D/g, '').length < 9) return toast('Укажите телефон', 'error')
    if (!picked.length) return toast('Добавьте хотя бы один товар', 'error')
    if (form.fulfillment === 'delivery' && form.delivery_address.trim().length < 5) {
      return toast('Укажите адрес доставки', 'error')
    }
    setBusy(true)
    try {
      await api('/admin/subscriptions', {
        method: 'POST',
        body: { ...form, items: picked },
      })
      toast('Регулярный заказ создан')
      setPicked([])
      setForm({ ...form, customer_name: '', phone: '', comment: '', delivery_address: '' })
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось создать подписку', 'error')
    } finally {
      setBusy(false)
    }
  }

  const patch = async (sub: Subscription, body: Record<string, unknown>, message: string) => {
    setBusy(true)
    try {
      await api(`/admin/subscriptions/${sub.id}`, { method: 'PATCH', body })
      toast(message)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось обновить подписку', 'error')
    } finally {
      setBusy(false)
    }
  }

  const runNow = async (sub: Subscription) => {
    if (!window.confirm(`Оформить заказ по подписке ${sub.customer_name} сейчас?`)) return
    setBusy(true)
    try {
      const result = await api<{ order_number: string }>(`/admin/subscriptions/${sub.id}/run`, {
        method: 'POST',
      })
      toast(`Создан заказ ${result.order_number}`)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось создать заказ', 'error')
    } finally {
      setBusy(false)
    }
  }

  if (features.loading) return <Loader label="Проверяем сервис" />

  if (!enabled) {
    return (
      <div className="empty-state">
        <div className="empty-state__icon"><Icon name="refresh" size={26} /></div>
        <h3>Регулярные заказы не подключены</h3>
        <p>Включите сервис, чтобы покупатели получали заказы по расписанию.</p>
        <Link to="/admin/services/subscriptions" className="btn btn--primary">Открыть сервис</Link>
      </div>
    )
  }

  if (loading) return <Loader label="Загружаем регулярные заказы" />
  if (error) {
    return (
      <div className="empty-state">
        <div className="empty-state__icon"><Icon name="alert" size={26} /></div>
        <h3>Не удалось загрузить подписки</h3>
        <p>{error}</p>
        <button type="button" className="btn btn--primary" onClick={reload}>Повторить</button>
      </div>
    )
  }

  return (
    <div className="subs-page">
      <section className="subs-stats">
        <div className="panel subs-stat">
          <span>Активные</span>
          <strong>{summary?.active ?? 0}</strong>
          <small>получают заказы</small>
        </div>
        <div className={`panel subs-stat ${(summary?.due ?? 0) > 0 ? 'is-warn' : ''}`}>
          <span>К оформлению</span>
          <strong>{summary?.due ?? 0}</strong>
          <small>дата уже наступила</small>
        </div>
        <div className="panel subs-stat">
          <span>Ближайшая неделя</span>
          <strong>{summary?.soon ?? 0}</strong>
          <small>заказов по расписанию</small>
        </div>
        <div className={`panel subs-stat ${(summary?.with_errors ?? 0) > 0 ? 'is-danger' : ''}`}>
          <span>Требуют внимания</span>
          <strong>{summary?.with_errors ?? 0}</strong>
          <small>ошибка при создании</small>
        </div>
      </section>

      {Boolean(data?.created_now?.length) && (
        <div className="panel subs-note">
          <Icon name="check" size={16} />
          <span>
            Автоматически созданы заказы:{' '}
            {data?.created_now?.map((order) => `${order.number} на ${formatMoney(order.total)}`).join(', ')}
          </span>
        </div>
      )}

      <div className="subs-layout">
        <section className="panel subs-board">
          <div className="subs-toolbar">
            <div className="services-tabs">
              {FILTERS.map((item) => (
                <button
                  key={item.code}
                  type="button"
                  className={filter === item.code ? 'is-active' : ''}
                  onClick={() => setFilter(item.code)}
                >
                  {item.title}
                </button>
              ))}
            </div>
            <input
              className="input"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Покупатель, телефон, товар"
            />
          </div>

          {visible.length ? (
            <div className="subs-list">
              {visible.map((sub) => (
                <article className={`subs-card subs-card--${sub.status}`} key={sub.id}>
                  <div className="subs-card__head">
                    <div>
                      <strong>{sub.customer_name}</strong>
                      <span>{sub.phone} · {sub.interval_label}</span>
                    </div>
                    <span className={`badge badge--${STATUS_TONE[sub.status] ?? 'muted'}`}>
                      {sub.status_label}
                    </span>
                  </div>

                  <div className="subs-card__meta">
                    <span className={sub.due_today ? 'is-warn' : ''}>
                      <Icon name="calendar" size={13} />
                      {sub.next_order_date ? humanDate(sub.next_order_date) : '—'}
                      {sub.overdue_days > 0 ? ` · просрочка ${sub.overdue_days} дн.` : ''}
                    </span>
                    <span><Icon name="box" size={13} /> {sub.items_count} поз. · {formatMoney(sub.total)}</span>
                    <span>
                      <Icon name={sub.fulfillment === 'delivery' ? 'car' : 'pin'} size={13} />
                      {sub.fulfillment === 'delivery' ? 'Доставка' : 'Самовывоз'}
                    </span>
                    {sub.last_order && (
                      <span><Icon name="check" size={13} /> заказ {sub.last_order.number}</span>
                    )}
                  </div>

                  <div className="subs-card__items">
                    {sub.items.map((item) => (
                      <span key={item.id} className={item.available ? '' : 'is-unavailable'}>
                        {item.title} × {item.quantity}
                      </span>
                    ))}
                  </div>

                  {sub.last_error && (
                    <p className="subs-card__error"><Icon name="alert" size={14} /> {sub.last_error}</p>
                  )}
                  {sub.comment && <p className="subs-card__comment">{sub.comment}</p>}

                  <div className="subs-card__actions">
                    {sub.status === 'active' && (
                      <>
                        <button type="button" className="btn btn--sm btn--primary" disabled={busy} onClick={() => void runNow(sub)}>
                          <Icon name="cart" size={14} /> Оформить сейчас
                        </button>
                        <button type="button" className="btn btn--sm btn--outline" disabled={busy} onClick={() => void patch(sub, { status: 'paused' }, 'Подписка на паузе')}>
                          Пауза
                        </button>
                      </>
                    )}
                    {sub.status === 'paused' && (
                      <button type="button" className="btn btn--sm btn--primary" disabled={busy} onClick={() => void patch(sub, { status: 'active' }, 'Подписка возобновлена')}>
                        <Icon name="refresh" size={14} /> Возобновить
                      </button>
                    )}
                    {sub.status !== 'cancelled' && (
                      <button type="button" className="btn btn--sm btn--ghost" disabled={busy} onClick={() => void patch(sub, { status: 'cancelled' }, 'Подписка отменена')}>
                        Отменить
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              icon="refresh"
              title="Регулярных заказов нет"
              text="Создайте первый заказ справа — дальше он повторяется сам."
            />
          )}
        </section>

        <aside className="panel subs-side">
          <div className="panel__head">
            <div>
              <h2>Новый регулярный заказ</h2>
              <p className="muted">Заказ создаётся автоматически в ближайшее свободное окно.</p>
            </div>
          </div>

          <div className="subs-form__row">
            <label className="field">
              <span className="field__label">Покупатель</span>
              <input className="input" value={form.customer_name} onChange={(event) => setForm({ ...form, customer_name: event.target.value })} placeholder="Имя" maxLength={120} />
            </label>
            <label className="field">
              <span className="field__label">Телефон</span>
              <input className="input" value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} placeholder="+375…" />
            </label>
          </div>

          <div className="subs-form__row">
            <label className="field">
              <span className="field__label">Повтор</span>
              <select className="input" value={form.interval_days} onChange={(event) => setForm({ ...form, interval_days: Number(event.target.value) })}>
                {INTERVALS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
            <label className="field">
              <span className="field__label">Первый заказ</span>
              <input className="input" type="date" value={form.next_order_date} onChange={(event) => setForm({ ...form, next_order_date: event.target.value })} />
            </label>
          </div>

          <div className="subs-form__row">
            <label className="field">
              <span className="field__label">Получение</span>
              <select className="input" value={form.fulfillment} onChange={(event) => setForm({ ...form, fulfillment: event.target.value as 'pickup' | 'delivery' })}>
                <option value="pickup">Самовывоз</option>
                <option value="delivery">Доставка</option>
              </select>
            </label>
            {form.fulfillment === 'delivery' && (
              <label className="field">
                <span className="field__label">Адрес</span>
                <input className="input" value={form.delivery_address} onChange={(event) => setForm({ ...form, delivery_address: event.target.value })} placeholder="Улица, дом, квартира" />
              </label>
            )}
          </div>

          <label className="field">
            <span className="field__label">Комментарий</span>
            <input className="input" value={form.comment} onChange={(event) => setForm({ ...form, comment: event.target.value })} placeholder="Пожелания к заказу" maxLength={600} />
          </label>

          <div className="subs-picker">
            <div className="subs-picker__head">
              <strong>Товары</strong>
              <span>{picked.length ? `${picked.length} поз. · ${formatMoney(pickedTotal)}` : 'ничего не выбрано'}</span>
            </div>
            <input
              className="input"
              type="search"
              value={productQuery}
              onChange={(event) => setProductQuery(event.target.value)}
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
                    <button type="button" onClick={() => removeProduct(item.product_id)} aria-label="Убрать">
                      <Icon name="trash" size={14} />
                    </button>
                  </div>
                )
              })}
            </div>
          )}

          <button type="button" className="btn btn--primary" disabled={busy} onClick={() => void create()}>
            <Icon name="refresh" size={16} /> {busy ? 'Сохраняем…' : 'Создать подписку'}
          </button>
          <p className="subs-side__hint">
            Покупатель видит подписку в личном кабинете и может поставить её на паузу.
          </p>
        </aside>
      </div>
    </div>
  )
}
