import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useApi } from '../lib/useApi'
import { assetUrl } from '../lib/api'
import { useSite } from '../store/SettingsContext'
import { useCart } from '../store/CartContext'
import { useToast } from '../store/ToastContext'
import { MarkdownText } from '../components/MarkdownText'
import { ProductCard } from '../components/ProductCard'
import { QtyControl, Loader, EmptyState } from '../components/ui'
import { Icon } from '../components/icons'
import type { Product } from '../lib/types'
import { formatMoney, formatQty, unitShort } from '../lib/format'

export default function ProductPage() {
  const { slug = '' } = useParams()
  const { site } = useSite()
  const { add } = useCart()
  const { toast } = useToast()
  const { data: product, loading, error } = useApi<Product>(`/products/${slug}`, false)
  const { data: related } = useApi<{ items: Product[] }>(`/products/${slug}/related`, false)
  const [quantity, setQuantity] = useState(1)

  useEffect(() => {
    if (product) {
      setQuantity(1)
      document.title = `${product.title} — ${site?.settings.brand_name ?? 'Рыбная лавка'}`
      window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior })
      return () => {
        document.title = site?.settings.seo_title ?? 'Рыбная лавка'
      }
    }
  }, [product, site])

  const total = useMemo(() => (product ? Math.round(product.final_price * quantity * 100) / 100 : 0), [product, quantity])

  if (loading) return <Loader label="Загружаем карточку товара…" />
  if (error || !product) {
    return (
      <div className="container section">
        <EmptyState
          icon="fish"
          title="Товар не найден"
          text="Возможно, позиция снята с продажи. Посмотрите другие товары в каталоге."
          action={<Link to="/catalog" className="btn btn--primary">В каталог</Link>}
        />
      </div>
    )
  }

  const s = site?.settings
  const unavailable = !product.can_order
  const hasDiscount = product.discount_percent > 0
  const nutrition = product.nutrition ?? {}
  const weightChips = product.unit === 'kg' ? [0.5, 1, 1.5, 2] : [1, 2, 3]

  return (
    <div className="product-page">
      <div className="container">
        <div className="breadcrumbs">
          <Link to="/">Главная</Link><Icon name="chevron-right" size={13} />
          <Link to="/catalog">Каталог</Link><Icon name="chevron-right" size={13} />
          {product.category_slug && (
            <>
              <Link to={`/catalog?category=${product.category_slug}`}>{product.category_title}</Link>
              <Icon name="chevron-right" size={13} />
            </>
          )}
          <span>{product.title}</span>
        </div>

        <div className="product-hero">
          <div className="product-hero__media">
            <div className="product-hero__image">
              {product.image_url ? <img src={assetUrl(product.image_url)} alt={product.title} /> : <Icon name="fish" size={100} />}
              <div className="product-hero__badges">
                {product.is_daily_deal && <span className="badge badge--gold">Товар дня</span>}
                {hasDiscount && <span className="badge badge--sale">Скидка {product.discount_percent}%</span>}
                {!unavailable ? (
                  <span className="badge badge--fresh"><span className="dot" /> В наличии</span>
                ) : (
                  <span className="badge badge--muted">Сегодня нет в наличии</span>
                )}
              </div>
            </div>
            <div className="product-hero__note">
              <Icon name="qr" size={20} />
              <span>В павильоне на эту рыбу наклеен QR-код — он ведёт на эту статью.</span>
            </div>
          </div>

          <div className="product-hero__info">
            <div className="product-hero__meta">
              {product.category_title && <span>{product.category_title}</span>}
              {product.origin && <><span className="dot-sep">·</span><span>{product.origin}</span></>}
              {product.season && <><span className="dot-sep">·</span><span>{product.season}</span></>}
            </div>
            <h1>{product.title}</h1>
            {product.subtitle && <p className="product-hero__subtitle">{product.subtitle}</p>}
            <p className="product-hero__desc">{product.short_description}</p>

            <div className="product-buy">
              <div className="product-buy__price">
                <div>
                  {hasDiscount && <span className="product-buy__old">{formatMoney(product.price)}</span>}
                  <strong>{formatMoney(product.final_price)}</strong>
                  <span className="product-buy__unit">/ {unitShort(product.unit)}</span>
                </div>
                {hasDiscount && (
                  <span className="product-buy__save">
                    Экономия {formatMoney((product.price - product.final_price) * quantity)}
                  </span>
                )}
              </div>

              <div className="product-buy__qty-head">
                <span className="field__label">{product.unit === 'kg' ? 'Вес' : 'Количество'}</span>
                {product.stock != null && <span className="muted">Осталось {formatQty(product.stock)} {unitShort(product.unit)}</span>}
              </div>

              <div className="product-buy__chips">
                {weightChips.map((value) => (
                  <button
                    key={value}
                    type="button"
                    className={quantity === value ? 'is-active' : ''}
                    onClick={() => setQuantity(value)}
                  >
                    {formatQty(value)} {unitShort(product.unit)}
                  </button>
                ))}
              </div>

              <div className="product-buy__controls">
                <QtyControl value={quantity} onChange={setQuantity} unit={product.unit} />
                <div className="product-buy__total">
                  <span>Итого</span>
                  <strong>{formatMoney(total)}</strong>
                </div>
              </div>

              <button
                type="button"
                className="btn btn--primary btn--lg btn--block"
                disabled={unavailable}
                onClick={() => {
                  add(product, quantity)
                  toast(`${product.title} — ${formatQty(quantity)} ${unitShort(product.unit)} в корзине`)
                }}
              >
                <Icon name="cart" size={19} />
                {unavailable ? 'Сегодня нет в наличии' : 'Добавить в корзину'}
              </button>

              {unavailable && (
                <div className="notice notice--warn">
                  <Icon name="alert" size={18} />
                  <span>Позиция временно недоступна. Позвоните в павильон — подскажем, когда будет привоз.</span>
                </div>
              )}

              <div className="product-buy__facts">
                <span><Icon name="clock" size={16} /> Забрать: {s?.city}, {s?.market_name}</span>
                <span><Icon name="wallet" size={16} /> Оплата при получении</span>
                <span><Icon name="shield" size={16} /> Документы о качестве</span>
              </div>
              {product.weight_note && <p className="product-buy__weightnote"><Icon name="scale" size={15} /> {product.weight_note}</p>}
            </div>
          </div>
        </div>

        <div className="product-content">
          <article className="product-article">
            <span className="eyebrow">Полезная статья</span>
            <h2>Всё о рыбе «{product.title}»</h2>
            <MarkdownText text={product.description} />

            {product.cooking_tips && (
              <div className="product-tip">
                <span className="product-tip__icon"><Icon name="scissors" size={22} /></span>
                <div><strong>Как приготовить</strong><p>{product.cooking_tips}</p></div>
              </div>
            )}
            {product.storage_tips && (
              <div className="product-tip product-tip--cool">
                <span className="product-tip__icon"><Icon name="shield" size={22} /></span>
                <div><strong>Хранение</strong><p>{product.storage_tips}</p></div>
              </div>
            )}
          </article>

          <aside className="product-side">
            <div className="nutrition-card">
              <h3>Пищевая ценность</h3>
              <p className="muted">на 100 г продукта</p>
              <dl>
                {nutrition.kcal != null && <div><dt>Калорийность</dt><dd>{nutrition.kcal} ккал</dd></div>}
                {nutrition.protein != null && <div><dt>Белки</dt><dd>{nutrition.protein} г</dd></div>}
                {nutrition.fat != null && <div><dt>Жиры</dt><dd>{nutrition.fat} г</dd></div>}
                {nutrition.omega3 != null && <div><dt>Омега-3</dt><dd>{nutrition.omega3} г</dd></div>}
              </dl>
              <p className="nutrition-card__note">
                Данные справочные. Пищевая ценность может незначительно отличаться в зависимости от партии.
              </p>
            </div>

            <div className="pickup-card">
              <h3><Icon name="pin" size={18} /> Где забрать</h3>
              <p>{s?.address}</p>
              <div className="pickup-card__row">
                <Icon name="clock" size={16} />
                <span>Сегодня: {s?.working_hours.find((day) => day.weekday === new Date().getDay() - (new Date().getDay() === 0 ? -6 : 1))?.open ?? '—'}–{s?.working_hours.find((day) => day.weekday === new Date().getDay() - (new Date().getDay() === 0 ? -6 : 1))?.close ?? '—'}</span>
              </div>
              <Link to="/pickup" className="link-arrow">Правила самовывоза <Icon name="arrow-right" size={16} /></Link>
            </div>

            <div className="quality-card">
              <span className="quality-card__icon"><Icon name="shield" size={24} /></span>
              <h3>Гарантия свежести</h3>
              <p>Принимаем рыбу малыми партиями, контролируем температуру и снимаем с продажи то, что не реализовано сегодня.</p>
            </div>
          </aside>
        </div>

        {related && related.items.length > 0 && (
          <section className="section section--related">
            <div className="section__head">
              <div><span className="eyebrow">Попробуйте также</span><h2>Похожие товары</h2></div>
              <Link to="/catalog" className="link-arrow">Весь каталог <Icon name="arrow-right" size={16} /></Link>
            </div>
            <div className="product-grid product-grid--four">
              {related.items.map((item) => <ProductCard key={item.id} product={item} />)}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
