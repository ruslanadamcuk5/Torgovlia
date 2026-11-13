import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useApi } from '../lib/useApi'
import { assetUrl } from '../lib/api'
import { storefrontBase, useSite } from '../store/SettingsContext'
import { MarkdownText } from '../components/MarkdownText'
import { ProductCard } from '../components/ProductCard'
import { Icon } from '../components/icons'
import { Loader } from '../components/ui'
import type { Product, Specialist } from '../lib/types'
import { formatMoney } from '../lib/format'

function durationLabel(minutes: number): string {
  if (!minutes) return 'по договорённости'
  if (minutes < 60) return `${minutes} мин`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `${hours} ч ${rest} мин` : `${hours} ч`
}

export default function ServicePage() {
  const { slug = '' } = useParams()
  const { site } = useSite()
  const { data: product, loading, error } = useApi<Product>(`/products/${slug}`, false)
  const { data: specialists } = useApi<{ items: Specialist[] }>(
    `/specialists${product ? `?service_id=${product.id}` : ''}`,
    false,
  )
  const { data: related } = useApi<{ items: Product[] }>(
    product?.category_slug ? `/services?category=${product.category_slug}&limit=4` : null,
    false,
  )

  useEffect(() => {
    if (!product) return
    document.title = `${product.title} — ${site?.settings.brand_name ?? 'Запись онлайн'}`
    const base = storefrontBase()
    let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')
    if (!canonical) {
      canonical = document.createElement('link')
      canonical.rel = 'canonical'
      document.head.appendChild(canonical)
    }
    canonical.href = `${base}/services/${product.slug}`
    let ld = document.getElementById('ld-service') as HTMLScriptElement | null
    if (!ld) {
      ld = document.createElement('script')
      ld.id = 'ld-service'
      ld.type = 'application/ld+json'
      document.head.appendChild(ld)
    }
    ld.textContent = JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'Service',
      name: product.title,
      description: product.short_description || product.description.slice(0, 300),
      image: product.image_url ? assetUrl(product.image_url) : undefined,
      provider: { '@type': 'LocalBusiness', name: site?.settings.brand_name ?? '' },
      offers: {
        '@type': 'Offer',
        price: product.final_price,
        priceCurrency: 'BYN',
        availability: product.can_order ? 'https://schema.org/InStock' : 'https://schema.org/OutOfStock',
      },
    })
    return () => document.getElementById('ld-service')?.remove()
  }, [product, site])

  if (loading) return <Loader label="Загружаем услугу…" />
  if (error || !product) {
    return (
      <div className="container section">
        <div className="empty-state">
          <span className="empty-state__icon"><Icon name="search" size={28} /></span>
          <h3>Услуга не найдена</h3>
          <p>Возможно, она скрыта или переименована.</p>
          <Link to="/services" className="btn btn--primary">Вернуться к услугам</Link>
        </div>
      </div>
    )
  }

  const people = specialists?.items ?? []
  const hasDiscount = product.discount_percent > 0

  return (
    <div className="product-page service-page">
      <div className="container">
        <div className="breadcrumbs">
          <Link to="/">Главная</Link><Icon name="chevron-right" size={13} />
          <Link to="/services">Услуги</Link><Icon name="chevron-right" size={13} />
          {product.category_slug && (
            <>
              <Link to={`/services?category=${product.category_slug}`}>{product.category_title}</Link>
              <Icon name="chevron-right" size={13} />
            </>
          )}
          <span>{product.title}</span>
        </div>

        <div className="product-hero">
          <div className="product-hero__media">
            <div className="product-hero__image">
              {product.image_url ? <img src={assetUrl(product.image_url)} alt={product.title} /> : <Icon name="sparkles" size={100} />}
              <div className="product-hero__badges">
                <span className="badge badge--fresh"><span className="dot" /> Онлайн-запись</span>
                {product.duration_minutes > 0 && <span className="badge badge--soft">{durationLabel(product.duration_minutes)}</span>}
                {hasDiscount && <span className="badge badge--sale">Скидка {product.discount_percent}%</span>}
              </div>
            </div>
            <div className="product-hero__note">
              <Icon name="calendar" size={20} />
              <span>Свободное время показывается по реальному графику специалистов.</span>
            </div>
          </div>

          <div className="product-hero__info">
            <div className="product-hero__meta">
              {product.category_title && <span>{product.category_title}</span>}
              {product.subtitle && <><span className="dot-sep">·</span><span>{product.subtitle}</span></>}
            </div>
            <h1>{product.title}</h1>
            <p className="product-hero__desc">{product.short_description}</p>

            <div className="service-facts">
              <div>
                <span>Длительность</span>
                <strong>{durationLabel(product.duration_minutes)}</strong>
              </div>
              <div>
                <span>Специалисты</span>
                <strong>{people.length || 'любой свободный'}</strong>
              </div>
              <div>
                <span>Запись</span>
                <strong>на {site?.settings.booking_days_ahead ?? 30} дней</strong>
              </div>
            </div>

            <div className="product-buy service-buy">
              <div className="product-buy__price">
                <div>
                  {hasDiscount && <span className="product-buy__old">{formatMoney(product.price)}</span>}
                  <strong>{formatMoney(product.final_price)}</strong>
                </div>
                <span className="muted">Оплата на месте после услуги</span>
              </div>

              <Link to={`/booking?service=${product.slug}`} className="btn btn--primary btn--lg btn--block">
                <Icon name="calendar" size={19} /> Выбрать время и записаться
              </Link>

              <div className="product-buy__facts">
                <span><Icon name="clock" size={16} /> {durationLabel(product.duration_minutes)}</span>
                <span><Icon name="wallet" size={16} /> Без предоплаты</span>
                <span><Icon name="check" size={16} /> Подтверждение сразу</span>
              </div>
            </div>
          </div>
        </div>

        {people.length > 0 && (
          <section className="section service-specialists">
            <div className="section__head">
              <div>
                <span className="eyebrow">Кто выполняет</span>
                <h2>Специалисты по услуге</h2>
              </div>
            </div>
            <div className="specialist-grid">
              {people.map((person) => (
                <article className="specialist-card" key={person.id}>
                  <div className="specialist-card__photo">
                    {person.photo_url ? (
                      <img src={assetUrl(person.photo_url)} alt={person.name} loading="lazy" />
                    ) : (
                      <span>{person.name.slice(0, 1)}</span>
                    )}
                  </div>
                  <div className="specialist-card__body">
                    <h3>{person.name}</h3>
                    <span className="specialist-card__role">{person.role}</span>
                    {person.bio && <p>{person.bio}</p>}
                    <Link to={`/booking?service=${product.slug}&specialist=${person.id}`} className="link-arrow">
                      Записаться к {person.name.split(' ')[0]} <Icon name="arrow-right" size={16} />
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        {product.description && (
          <section className="section">
            <article className="product-article service-article">
              <span className="eyebrow">Подробнее</span>
              <h2>Об услуге «{product.title}»</h2>
              <MarkdownText text={product.description} />
            </article>
          </section>
        )}

        {(related?.items.length ?? 0) > 0 && (
          <section className="section">
            <div className="section__head">
              <div>
                <span className="eyebrow">Рядом</span>
                <h2>Другие услуги направления</h2>
              </div>
              <Link to={`/services?category=${product.category_slug}`} className="link-arrow">
                Все услуги <Icon name="arrow-right" size={17} />
              </Link>
            </div>
            <div className="product-grid product-grid--four">
              {related!.items.filter((item) => item.id !== product.id).slice(0, 4).map((item) => (
                <ProductCard key={item.id} product={item} />
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
