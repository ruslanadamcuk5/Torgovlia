import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useApi } from '../lib/useApi'
import { api, assetUrl } from '../lib/api'
import { storefrontBase, useSite } from '../store/SettingsContext'
import { useCart } from '../store/CartContext'
import { useAuth } from '../store/AuthContext'
import { useToast } from '../store/ToastContext'
import { MarkdownText } from '../components/MarkdownText'
import { ProductCard } from '../components/ProductCard'
import { QtyControl, Loader, EmptyState, Spinner } from '../components/ui'
import { Icon } from '../components/icons'
import type { Product, ReviewList } from '../lib/types'
import { formatMoney, formatQty, humanDate, unitShort } from '../lib/format'

const REVIEW_EMPTY = { name: '', phone: '', rating: 5, text: '', orderNumber: '', consent: false }

function Stars({ value, size = 15 }: { value: number; size?: number }) {
  const rounded = Math.round(value)
  return (
    <span className="stars" style={{ fontSize: size }} aria-label={`Рейтинг ${value} из 5`}>
      {[1, 2, 3, 4, 5].map((star) => (
        <span key={star} className={star <= rounded ? 'stars__item is-on' : 'stars__item'}>★</span>
      ))}
    </span>
  )
}

export default function ProductPage() {
  const { slug = '' } = useParams()
  const { site } = useSite()
  const { add } = useCart()
  const { user } = useAuth()
  const { toast } = useToast()
  const { data: product, loading, error } = useApi<Product>(`/products/${slug}`, false)
  const { data: related } = useApi<{ items: Product[] }>(`/products/${slug}/related`, false)
  const { data: reviews, reload: reloadReviews } = useApi<ReviewList>(`/products/${slug}/reviews`, false)
  const [quantity, setQuantity] = useState(1)
  const [reviewForm, setReviewForm] = useState(REVIEW_EMPTY)
  const [reviewBusy, setReviewBusy] = useState(false)
  const [reviewError, setReviewError] = useState('')
  const [reviewSent, setReviewSent] = useState(false)

  useEffect(() => {
    if (user) {
      setReviewForm((current) => ({
        ...current,
        name: current.name || user.full_name || '',
        phone: current.phone || user.phone || '',
      }))
    }
  }, [user])

  const setReview = <K extends keyof typeof REVIEW_EMPTY>(key: K, value: (typeof REVIEW_EMPTY)[K]) => {
    setReviewForm((current) => ({ ...current, [key]: value }))
  }

  const submitReview = async () => {
    setReviewError('')
    if (reviewForm.name.trim().length < 2) return setReviewError('Укажите имя')
    if (reviewForm.phone.replace(/\D/g, '').length < 9) return setReviewError('Укажите телефон для связи')
    if (reviewForm.text.trim().length < 5) return setReviewError('Расскажите подробнее — хотя бы несколько слов')
    if (!reviewForm.consent) return setReviewError('Нужно согласие на обработку персональных данных')

    setReviewBusy(true)
    try {
      await api(`/products/${slug}/reviews`, {
        method: 'POST',
        body: {
          customer_name: reviewForm.name.trim(),
          phone: reviewForm.phone,
          rating: reviewForm.rating,
          text: reviewForm.text.trim(),
          order_number: reviewForm.orderNumber.trim(),
          consent_personal_data: reviewForm.consent,
        },
      })
      setReviewSent(true)
      setReviewForm({ ...REVIEW_EMPTY, name: reviewForm.name, phone: reviewForm.phone })
      toast('Спасибо! Отзыв появится после проверки')
    } catch (err) {
      setReviewError(err instanceof Error ? err.message : 'Не удалось отправить отзыв')
    } finally {
      setReviewBusy(false)
    }
  }

  useEffect(() => {
    if (product) {
      setQuantity(1)
      document.title = `${product.title} — ${site?.settings.brand_name ?? 'Рыбная лавка'}`
      window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior })

      const base = storefrontBase()
      const url = `${base}/fish/${product.slug}`
      const image = product.image_url ? assetUrl(product.image_url) : ''
      let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')
      if (!canonical) {
        canonical = document.createElement('link')
        canonical.rel = 'canonical'
        document.head.appendChild(canonical)
      }
      const previousCanonical = canonical.href
      canonical.href = url
      const meta = (key: string, content: string, attr: 'name' | 'property' = 'property') => {
        let tag = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${key}"]`)
        if (!tag) {
          tag = document.createElement('meta')
          tag.setAttribute(attr, key)
          document.head.appendChild(tag)
        }
        tag.setAttribute('content', content)
      }
      meta('og:type', 'product')
      meta('og:url', url)
      meta('og:title', `${product.title} — ${site?.settings.brand_name ?? ''}`)
      meta('og:description', product.short_description || product.subtitle)
      if (image) {
        meta('og:image', image)
        meta('twitter:image', image, 'name')
      }
      meta('twitter:card', image ? 'summary_large_image' : 'summary', 'name')

      let ld = document.getElementById('ld-product') as HTMLScriptElement | null
      if (!ld) {
        ld = document.createElement('script')
        ld.id = 'ld-product'
        ld.type = 'application/ld+json'
        document.head.appendChild(ld)
      }
      ld.textContent = JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'Product',
        name: product.title,
        description: product.short_description || product.description.slice(0, 300),
        image: image ? [image] : undefined,
        sku: product.slug,
        category: product.category_title ?? undefined,
        brand: { '@type': 'Brand', name: site?.settings.brand_name ?? '' },
        offers: {
          '@type': 'Offer',
          url,
          price: product.final_price.toFixed(2),
          priceCurrency: 'BYN',
          availability: product.is_available ? 'https://schema.org/InStock' : 'https://schema.org/OutOfStock',
          seller: { '@type': 'Organization', name: site?.settings.brand_name ?? '' },
        },
        aggregateRating:
          product.rating && product.reviews_count
            ? {
                '@type': 'AggregateRating',
                ratingValue: product.rating.toFixed(1),
                reviewCount: product.reviews_count,
              }
            : undefined,
      })

      return () => {
        document.title = site?.settings.seo_title ?? 'Рыбная лавка'
        document.getElementById('ld-product')?.remove()
        if (previousCanonical) canonical.href = previousCanonical
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
  const rating = product.rating ?? 0
  const reviewsCount = product.reviews_count ?? 0
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
            {reviewsCount > 0 && (
              <div className="product-rating-line">
                <Stars value={rating} />
                <span>{rating.toFixed(1)} · {reviewsCount} {reviewsCount === 1 ? 'отзыв' : 'отзывов'}</span>
              </div>
            )}
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

        {reviews?.enabled && (
          <section className="section reviews-section" id="reviews">
            <div className="reviews-layout">
              <div className="reviews-main">
                <div className="section__head">
                  <div>
                    <span className="eyebrow">Мнения покупателей</span>
                    <h2>Отзывы о товаре</h2>
                  </div>
                  {reviews.total > 0 && (
                    <div className="reviews-score">
                      <strong>{reviews.average.toFixed(1)}</strong>
                      <div className="reviews-score__meta">
                        <Stars value={reviews.average} size={16} />
                        <span className="muted">{reviews.total} {reviews.total === 1 ? 'отзыв' : 'отзывов'}</span>
                      </div>
                    </div>
                  )}
                </div>

                {reviews.items.length === 0 ? (
                  <p className="muted reviews-empty">
                    Пока нет опубликованных отзывов. Станьте первым — расскажите, как вам товар.
                  </p>
                ) : (
                  <div className="review-list">
                    {reviews.items.map((review) => (
                      <article key={review.id} className="review-card">
                        <header>
                          <strong>{review.customer_name}</strong>
                          <Stars value={review.rating} size={13} />
                          {review.is_verified_purchase && (
                            <span className="badge badge--fresh">Покупка подтверждена</span>
                          )}
                        </header>
                        <p>{review.text}</p>
                        {review.created_at && (
                          <time>{humanDate(review.created_at.slice(0, 10))}</time>
                        )}
                      </article>
                    ))}
                  </div>
                )}
              </div>

              <aside className="review-form">
                <h3>Оставить отзыв</h3>
                {reviewSent ? (
                  <div className="notice notice--info">
                    <Icon name="check" size={18} />
                    <span>Спасибо! Отзыв отправлен на проверку и скоро появится на сайте.</span>
                  </div>
                ) : (
                  <>
                    <p className="muted">Отзыв публикуется после проверки владельцем магазина.</p>
                    <label className="field">
                      <span className="field__label">Имя</span>
                      <input
                        className="input"
                        value={reviewForm.name}
                        onChange={(event) => setReview('name', event.target.value)}
                        placeholder="Как к вам обращаться"
                        maxLength={80}
                      />
                    </label>
                    <label className="field">
                      <span className="field__label">Телефон</span>
                      <input
                        className="input"
                        value={reviewForm.phone}
                        onChange={(event) => setReview('phone', event.target.value)}
                        placeholder="+375 29 000-00-00"
                        inputMode="tel"
                      />
                      <span className="field__hint">Не публикуется — нужен только для связи.</span>
                    </label>
                    <div className="field">
                      <span className="field__label">Оценка</span>
                      <div className="review-stars-input">
                        {[1, 2, 3, 4, 5].map((star) => (
                          <button
                            key={star}
                            type="button"
                            className={star <= reviewForm.rating ? 'is-on' : ''}
                            onClick={() => setReview('rating', star)}
                            aria-label={`${star} из 5`}
                          >
                            ★
                          </button>
                        ))}
                      </div>
                    </div>
                    <label className="field">
                      <span className="field__label">Отзыв</span>
                      <textarea
                        className="textarea"
                        value={reviewForm.text}
                        onChange={(event) => setReview('text', event.target.value)}
                        placeholder="Что понравилось, как готовили, что запомнилось"
                        rows={4}
                        maxLength={1200}
                      />
                    </label>
                    <label className="field">
                      <span className="field__label">Номер брони</span>
                      <input
                        className="input"
                        value={reviewForm.orderNumber}
                        onChange={(event) => setReview('orderNumber', event.target.value.toUpperCase())}
                        placeholder="Необязательно — подтвердит покупку"
                        maxLength={24}
                      />
                    </label>
                    <label className="checkbox">
                      <input
                        type="checkbox"
                        checked={reviewForm.consent}
                        onChange={(event) => setReview('consent', event.target.checked)}
                      />
                      <span>Согласен на обработку персональных данных</span>
                    </label>
                    {reviewError && (
                      <div className="notice notice--error">
                        <Icon name="alert" size={16} />
                        <span>{reviewError}</span>
                      </div>
                    )}
                    <button
                      type="button"
                      className="btn btn--primary btn--block"
                      onClick={submitReview}
                      disabled={reviewBusy}
                    >
                      {reviewBusy ? <Spinner size={17} /> : <Icon name="send" size={17} />}
                      Отправить отзыв
                    </button>
                  </>
                )}
              </aside>
            </div>
          </section>
        )}

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
