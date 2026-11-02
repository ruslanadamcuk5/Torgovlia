import { Link } from 'react-router-dom'
import type { Order } from '../lib/types'
import { formatMoney, formatQty, humanDate, statusLabel, unitShort } from '../lib/format'
import { Icon } from './icons'
import { StatusBadge } from './ui'

export function OrderCard({ order, onCancel, busy = false }: { order: Order; onCancel?: (order: Order) => void; busy?: boolean }) {
  const canCancel = onCancel && (order.status === 'new' || order.status === 'confirmed')
  return (
    <article className="order-card">
      <header className="order-card__head">
        <div>
          <span className="order-card__label">Бронь</span>
          <strong className="order-card__number">{order.number}</strong>
        </div>
        <StatusBadge status={order.status} />
      </header>

      <div className="order-card__grid">
        <div><span>Получение</span><strong>{humanDate(order.pickup_date)}, {order.pickup_time}</strong></div>
        <div><span>Сумма</span><strong>{formatMoney(order.total_amount)}</strong></div>
        <div><span>Позиций</span><strong>{order.items_count}</strong></div>
        <div><span>Создана</span><strong>{new Date(order.created_at).toLocaleDateString('ru-BY')}</strong></div>
      </div>

      <details className="order-card__details">
        <summary>Состав заказа <Icon name="chevron-down" size={17} /></summary>
        <ul>
          {order.items.map((item) => (
            <li key={item.id}>
              <span>{item.title}</span>
              <span>{formatQty(item.quantity)} {unitShort(item.unit)} · {formatMoney(item.line_total)}</span>
            </li>
          ))}
        </ul>
      </details>

      {order.admin_comment && (
        <div className="order-card__comment"><Icon name="info" size={16} /> {order.admin_comment}</div>
      )}
      {order.comment && (
        <div className="order-card__comment order-card__comment--client"><Icon name="edit" size={16} /> Ваш комментарий: {order.comment}</div>
      )}

      <footer className="order-card__foot">
        <Link to="/pickup" className="order-card__hint">
          <Icon name="pin" size={16} /> Самовывоз из павильона
        </Link>
        {canCancel && (
          <button type="button" className="btn btn--sm btn--danger-ghost" onClick={() => onCancel?.(order)} disabled={busy}>
            <Icon name="close" size={15} /> Отменить
          </button>
        )}
      </footer>
    </article>
  )
}

export function StatusTimeline({ order }: { order: Order }) {
  const stages = ['new', 'confirmed', 'ready', 'completed']
  const currentIndex = Math.max(0, stages.indexOf(order.status))
  const cancelled = order.status === 'cancelled' || order.status === 'rejected'
  return (
    <div className={`timeline ${cancelled ? 'timeline--cancelled' : ''}`}>
      {stages.map((stage, index) => (
        <div key={stage} className={`timeline__step ${index <= currentIndex && !cancelled ? 'is-done' : ''} ${cancelled && index === 0 ? 'is-done' : ''}`}>
          <span className="timeline__dot">{index < currentIndex && !cancelled ? <Icon name="check" size={12} /> : index + 1}</span>
          <span>{statusLabel(stage)}</span>
        </div>
      ))}
    </div>
  )
}
