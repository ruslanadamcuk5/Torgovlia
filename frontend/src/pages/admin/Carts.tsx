import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Loader } from '../../components/ui'
import { Icon } from '../../components/icons'
import { formatMoney } from '../../lib/format'

interface CartItem {
  product_id: number
  slug: string
  title: string
  unit: string
  price: number
  quantity: number
  image_url: string
}

interface CartRow {
  id: number
  name: string
  phone: string
  phone_raw: string
  email: string
  items: CartItem[]
  items_count: number
  total: number
  status: 'active' | 'converted'
  abandoned: boolean
  reminder_count: number
  reminded_at: string | null
  last_activity_at: string
  created_at: string
}

interface CartsData {
  items: CartRow[]
  total: number
  summary: {
    abandoned: number
    abandoned_value: number
    with_contact: number
    active: number
  }
  threshold_minutes: number
}

type Tab = 'abandoned' | 'active' | 'converted' | 'all'

const TABS: { code: Tab; title: string }[] = [
  { code: 'abandoned', title: 'Брошенные' },
  { code: 'active', title: 'Сейчас в корзинах' },
  { code: 'converted', title: 'Оформленные' },
  { code: 'all', title: 'Все' },
]

export default function Carts() {
  const { toast } = useToast()
  const { data: features, loading: featuresLoading } = useApi<{ services: Record<string, boolean> }>(
    '/admin/services/features',
  )
  const enabled = Boolean(features?.services.abandoned_cart)
  const [tab, setTab] = useState<Tab>('abandoned')
  const { data, loading, reload } = useApi<CartsData>(
    enabled ? `/admin/carts?status=${tab}&limit=120` : null,
  )
  const [busy, setBusy] = useState<number | 'all' | null>(null)

  const items = data?.items ?? []
  const contactable = useMemo(() => items.filter((row) => row.email || row.phone), [items])

  const remind = async (cart: CartRow) => {
    setBusy(cart.id)
    try {
      const result = await api<{ sent: boolean; demo: boolean; channel: string; contact: string }>(
        `/admin/carts/${cart.id}/remind`,
        { method: 'POST' },
      )
      toast(
        result.demo
          ? `Демо-напоминание на ${result.contact} (реально не отправлено)`
          : `Напоминание отправлено на ${result.contact}`,
      )
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось отправить напоминание', 'error')
    } finally {
      setBusy(null)
    }
  }

  const remindAll = async () => {
    if (!window.confirm('Отправить напоминания всем брошенным корзинам с контактом?')) return
    setBusy('all')
    try {
      const result = await api<{ sent: number; demo: number; skipped: number; failed: number }>(
        '/admin/carts/remind-all',
        { method: 'POST' },
      )
      toast(
        `Отправлено ${result.sent}${result.demo ? ` (демо ${result.demo})` : ''}, пропущено ${result.skipped}, ошибок ${result.failed}`,
      )
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось разослать напоминания', 'error')
    } finally {
      setBusy(null)
    }
  }

  const dismiss = async (cart: CartRow) => {
    if (!window.confirm('Убрать корзину из списка? Товары у покупателя останутся.')) return
    try {
      await api(`/admin/carts/${cart.id}`, { method: 'DELETE' })
      reload()
      toast('Корзина убрана')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось убрать корзину', 'error')
    }
  }

  if (featuresLoading) return <Loader />

  if (!enabled) {
    return (
      <div className="admin-page">
        <section className="panel panel--accent">
          <div className="panel__head"><h2>Брошенные корзины</h2></div>
          <p>
            Напоминания о брошенной корзине доступны на тарифе <strong>«Про»</strong>.
            Магазин сохраняет корзины покупателей и возвращает их письмом или SMS.
          </p>
          <Link to="/admin/services" className="btn btn--primary">
            Перейти к сервисам <Icon name="arrow-right" size={17} />
          </Link>
        </section>
      </div>
    )
  }

  return (
    <div className="admin-page carts-page">
      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Брошенные корзины</h2>
            <p className="muted">
              Корзина считается брошенной через {data?.threshold_minutes ?? 60} минут без действий.
              Напомнить можно письмом или SMS, повторно — не чаще раза в сутки.
            </p>
          </div>
          <button
            type="button"
            className="btn btn--primary"
            onClick={remindAll}
            disabled={busy === 'all' || !data?.summary.abandoned}
          >
            <Icon name="send" size={16} /> Напомнить всем
          </button>
        </div>

        <div className="carts-stats">
          <div><span>Брошено</span><strong>{data?.summary.abandoned ?? 0}</strong></div>
          <div><span>Сумма</span><strong>{formatMoney(data?.summary.abandoned_value ?? 0)}</strong></div>
          <div><span>С контактом</span><strong>{data?.summary.with_contact ?? 0}</strong></div>
          <div><span>Активных сейчас</span><strong>{data?.summary.active ?? 0}</strong></div>
        </div>

        <div className="carts-tabs" role="tablist">
          {TABS.map((item) => (
            <button
              key={item.code}
              type="button"
              role="tab"
              aria-selected={tab === item.code}
              className={tab === item.code ? 'is-active' : ''}
              onClick={() => setTab(item.code)}
            >
              {item.title}
              {item.code === 'abandoned' && data?.summary.abandoned ? ` · ${data.summary.abandoned}` : ''}
            </button>
          ))}
        </div>

        {loading && <p className="muted">Загружаем корзины…</p>}

        <div className="carts-list">
          {items.map((cart) => (
            <div className={`cart-row${cart.abandoned ? ' is-abandoned' : ''}`} key={cart.id}>
              <div className="cart-row__head">
                <div className="cart-row__who">
                  <strong>{cart.name}</strong>
                  <small>
                    {cart.phone || 'без телефона'}
                    {cart.email ? ` · ${cart.email}` : ''}
                  </small>
                </div>
                <span className={`cart-row__status cart-row__status--${cart.abandoned ? 'abandoned' : cart.status}`}>
                  {cart.abandoned ? 'Брошена' : cart.status === 'converted' ? 'Оформлена' : 'Активна'}
                </span>
                <div className="cart-row__sum">
                  <strong>{formatMoney(cart.total)}</strong>
                  <small>{cart.items_count} поз. · {new Date(cart.last_activity_at).toLocaleString('ru-BY')}</small>
                </div>
                <div className="cart-row__actions">
                  <button
                    type="button"
                    className="btn btn--sm btn--ghost"
                    onClick={() => remind(cart)}
                    disabled={busy === cart.id || (!cart.email && !cart.phone) || !!(
                      cart.reminded_at && Date.now() - new Date(cart.reminded_at).getTime() < 24 * 3600 * 1000
                    )}
                    title={cart.reminder_count ? `Напоминали ${cart.reminder_count} раз` : undefined}
                  >
                    {busy === cart.id ? '…' : 'Напомнить'}
                  </button>
                  <button type="button" className="btn btn--sm btn--ghost" onClick={() => dismiss(cart)}>
                    Убрать
                  </button>
                </div>
              </div>
              <div className="cart-row__items">
                {cart.items.slice(0, 6).map((item) => (
                  <span key={`${cart.id}-${item.product_id}`}>
                    {item.title} · {item.quantity} {item.unit === 'kg' ? 'кг' : 'шт.'}
                  </span>
                ))}
                {cart.items.length > 6 && <span className="muted">и ещё {cart.items.length - 6}</span>}
              </div>
              {cart.reminded_at && (
                <small className="cart-row__reminded">
                  Напоминание: {new Date(cart.reminded_at).toLocaleString('ru-BY')} · всего {cart.reminder_count}
                </small>
              )}
            </div>
          ))}
          {!loading && items.length === 0 && (
            <div className="carts-empty">
              <Icon name="cart" size={22} />
              <p>
                {tab === 'abandoned'
                  ? 'Брошенных корзин пока нет. Как только покупатель оставит товары и уйдёт, корзина появится здесь.'
                  : 'В этом списке пусто.'}
              </p>
            </div>
          )}
        </div>

        {contactable.length > 0 && tab === 'abandoned' && (
          <p className="muted carts-note">
            Напоминание уходит на почту, если она есть, иначе на телефон. На демо-стенде отправка
            имитируется и помечается как «демо».
          </p>
        )}
      </section>
    </div>
  )
}
