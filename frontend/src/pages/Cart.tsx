import { Link, useNavigate } from 'react-router-dom'
import { assetUrl } from '../lib/api'
import { useSite } from '../store/SettingsContext'
import { useCart } from '../store/CartContext'
import { QtyControl, EmptyState } from '../components/ui'
import { Icon } from '../components/icons'
import { formatMoney, formatQty, unitShort } from '../lib/format'

export default function Cart() {
  const { site } = useSite()
  const { lines, setQuantity, remove, clear, subtotal, count } = useCart()
  const navigate = useNavigate()

  if (!site) return null
  const s = site.settings
  const belowMin = subtotal < s.min_order_amount
  const missing = Math.max(0, s.min_order_amount - subtotal)

  if (count === 0) {
    return (
      <div className="container section">
        <div className="page-head page-head--compact">
          <div className="breadcrumbs"><Link to="/">Главная</Link><Icon name="chevron-right" size={13} /><span>Корзина</span></div>
          <h1>Корзина</h1>
        </div>
        <EmptyState
          icon="cart"
          title="Пока пусто"
          text="Добавьте рыбу или морепродукты из каталога — соберём бронь к вашему приходу."
          action={<Link to="/catalog" className="btn btn--primary">Перейти в каталог <Icon name="arrow-right" size={17} /></Link>}
        />
      </div>
    )
  }

  return (
    <div className="container section cart-page">
      <div className="breadcrumbs"><Link to="/">Главная</Link><Icon name="chevron-right" size={13} /><Link to="/catalog">Каталог</Link><Icon name="chevron-right" size={13} /><span>Корзина</span></div>
      <div className="page-head__row page-head__row--tight">
        <div>
          <h1>Ваша бронь</h1>
          <p className="page-head__sub">{count} {count === 1 ? 'позиция' : 'позиции'} · самовывоз из павильона</p>
        </div>
        <button type="button" className="btn btn--ghost btn--sm" onClick={() => { if (window.confirm('Очистить корзину?')) clear() }}>
          <Icon name="trash" size={16} /> Очистить
        </button>
      </div>

      <div className="cart-layout">
        <div className="cart-list">
          {lines.map((line) => (
            <article className={`cart-item ${!line.is_available ? 'is-unavailable' : ''}`} key={line.productId}>
              <Link to={`/fish/${line.slug}`} className="cart-item__media">
                {line.image_url ? <img src={assetUrl(line.image_url)} alt={line.title} /> : <Icon name="fish" size={36} />}
              </Link>
              <div className="cart-item__info">
                <Link to={`/fish/${line.slug}`} className="cart-item__title">{line.title}</Link>
                <span className="cart-item__price">{formatMoney(line.price)} / {unitShort(line.unit)}</span>
                {!line.is_available && <span className="cart-item__warn">Сегодня нет в наличии — уберите позицию</span>}
                <div className="cart-item__controls">
                  <QtyControl value={line.quantity} onChange={(value) => setQuantity(line.productId, value)} unit={line.unit} compact />
                  <button type="button" className="icon-btn icon-btn--danger" onClick={() => remove(line.productId)} aria-label="Удалить">
                    <Icon name="trash" size={18} />
                  </button>
                </div>
              </div>
              <div className="cart-item__total">
                <strong>{formatMoney(line.price * line.quantity)}</strong>
                <span>{formatQty(line.quantity)} {unitShort(line.unit)}</span>
              </div>
            </article>
          ))}

          <div className="cart-note">
            <Icon name="info" size={20} />
            <p>
              Итоговая стоимость весового товара может отличаться на ±5% — она рассчитывается по фактическому весу при выдаче.
              Предоплата не требуется.
            </p>
          </div>
        </div>

        <aside className="cart-summary">
          <h2>Итого</h2>
          <dl>
            <div><dt>Товаров</dt><dd>{count}</dd></div>
            <div><dt>Сумма</dt><dd>{formatMoney(subtotal)}</dd></div>
            <div><dt>Доставка</dt><dd>самовывоз</dd></div>
            <div><dt>Оплата</dt><dd>при получении</dd></div>
          </dl>

          {belowMin && (
            <div className="notice notice--warn">
              <Icon name="alert" size={18} />
              <span>До минимальной суммы брони не хватает <strong>{formatMoney(missing)}</strong></span>
            </div>
          )}

          <div className="cart-summary__total">
            <span>К оплате в павильоне</span>
            <strong>{formatMoney(subtotal)}</strong>
          </div>

          <button
            type="button"
            className="btn btn--primary btn--lg btn--block"
            disabled={belowMin || lines.some((line) => !line.is_available)}
            onClick={() => navigate('/checkout')}
          >
            Оформить бронь <Icon name="arrow-right" size={18} />
          </button>
          <Link to="/catalog" className="btn btn--ghost btn--block">Добавить ещё</Link>

          <div className="cart-summary__pickup">
            <Icon name="pin" size={18} />
            <div>
              <strong>Где забрать</strong>
              <span>{s.city}, {s.market_name}, {s.pavilion}</span>
            </div>
          </div>
          <p className="cart-summary__note">{s.payment_note}</p>
        </aside>
      </div>
    </div>
  )
}
