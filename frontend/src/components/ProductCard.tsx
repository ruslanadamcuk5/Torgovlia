import { Link } from 'react-router-dom'
import { assetUrl } from '../lib/api'
import type { Product } from '../lib/types'
import { formatMoney, formatQty, unitShort } from '../lib/format'
import { useCart } from '../store/CartContext'
import { useToast } from '../store/ToastContext'
import { Icon } from './icons'

export function ProductImage({ product, className = '' }: { product: Product; className?: string }) {
  return (
    <div className={`product-image ${className}`}>
      {product.image_url ? (
        <img src={assetUrl(product.image_url)} alt={product.title} loading="lazy" />
      ) : (
        <span className="product-image__fallback"><Icon name="fish" size={46} /></span>
      )}
    </div>
  )
}

export function ProductCard({ product, featured = false }: { product: Product; featured?: boolean }) {
  const { add, lines } = useCart()
  const { toast } = useToast()
  const inCart = lines.find((line) => line.productId === product.id)
  const unavailable = !product.can_order
  const hasDiscount = product.discount_percent > 0

  return (
    <article className={`product-card ${featured ? 'product-card--featured' : ''} ${unavailable ? 'is-unavailable' : ''}`}>
      <Link to={`/fish/${product.slug}`} className="product-card__media">
        <ProductImage product={product} />
        <div className="product-card__badges">
          {product.is_daily_deal && <span className="badge badge--gold">Товар дня</span>}
          {hasDiscount && <span className="badge badge--sale">−{product.discount_percent}%</span>}
          {product.badges.filter((badge) => badge !== 'Товар дня' && !badge.includes('−')).slice(0, 1).map((badge) => (
            <span key={badge} className="badge badge--soft">{badge}</span>
          ))}
        </div>
        {unavailable && <span className="product-card__unavailable">Сегодня нет в наличии</span>}
      </Link>

      <div className="product-card__body">
        <div className="product-card__meta">
          {product.category_title && <span>{product.category_title}</span>}
          {product.origin && <span className="dot-sep">·</span>}
          {product.origin && <span>{product.origin}</span>}
        </div>
        <h3 className="product-card__title">
          <Link to={`/fish/${product.slug}`}>{product.title}</Link>
        </h3>
        <p className="product-card__desc">{product.short_description}</p>

        {(product.reviews_count ?? 0) > 0 && (
          <div className="product-card__rating">
            <span className="product-card__star">★</span>
            {(product.rating ?? 0).toFixed(1)}
            <span className="muted">· {product.reviews_count} {product.reviews_count === 1 ? 'отзыв' : 'отзывов'}</span>
          </div>
        )}

        <div className="product-card__foot">
          <div className="product-card__price">
            {hasDiscount && <span className="product-card__old">{formatMoney(product.price)}</span>}
            <strong>{formatMoney(product.final_price)}</strong>
            <span className="product-card__unit">/ {unitShort(product.unit)}</span>
          </div>
          <button
            type="button"
            className={`btn btn--sm ${inCart ? 'btn--success' : 'btn--primary'}`}
            disabled={unavailable}
            onClick={() => {
              add(product, 1)
              toast(`${product.title} — добавлено в корзину`)
            }}
          >
            <Icon name={inCart ? 'check' : 'cart'} size={17} />
            {unavailable ? 'Нет в наличии' : inCart ? `В корзине · ${formatQty(inCart.quantity)}` : 'В корзину'}
          </button>
        </div>
      </div>
    </article>
  )
}
