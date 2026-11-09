import type { CSSProperties } from 'react'
import { Icon } from './icons'
import type { DesignTemplate } from '../lib/types'
import { formatMoney } from '../lib/format'
import { applyAccent } from '../lib/theme'

interface TemplatePreviewProps {
  template: DesignTemplate | null
  accent?: string
  brand: string
  tagline: string
  heroBadge: string
  heroTitle: string
  heroSubtitle: string
  phone: string
  logo?: string
  heroImage?: string
}

const SAMPLE = [
  { icon: 'box' as const, title: 'Товар дня', price: 29.9 },
  { icon: 'star' as const, title: 'Хит продаж', price: 42.0 },
  { icon: 'heart' as const, title: 'Новинка', price: 18.5 },
]

export function TemplatePreview({
  template,
  accent,
  brand,
  tagline,
  heroBadge,
  heroTitle,
  heroSubtitle,
  phone,
  logo,
  heroImage,
}: TemplatePreviewProps) {
  const tokens = applyAccent(template?.tokens ?? {}, accent)
  const style = Object.fromEntries(
    Object.entries(tokens).map(([key, value]) => [`--${key}`, value]),
  ) as CSSProperties

  const heading = heroTitle || tagline || brand || 'Ваш магазин'

  return (
    <div className="tpl-preview" style={style} aria-label="Предпросмотр витрины">
      <div className="tpl-preview__bar">
        <span className="tpl-preview__brand">
          {logo ? (
            <img src={logo} alt="" className="tpl-preview__logo" />
          ) : (
            <span className="tpl-preview__mark">{(brand || 'М').slice(0, 1).toUpperCase()}</span>
          )}
          <strong>{brand || 'Ваш магазин'}</strong>
        </span>
        <span className="tpl-preview__nav">
          <span>Каталог</span>
          <span>Доставка</span>
          <span>Контакты</span>
        </span>
        {phone && <span className="tpl-preview__phone">{phone}</span>}
      </div>

      <div className="tpl-preview__hero">
        <div className="tpl-preview__hero-text">
          {heroBadge && <span className="tpl-preview__badge">{heroBadge}</span>}
          <h3>{heading}</h3>
          {heroSubtitle && <p>{heroSubtitle}</p>}
          <span className="tpl-preview__cta">
            <span className="tpl-preview__button">Смотреть каталог</span>
            <span className="tpl-preview__button tpl-preview__button--ghost">Заказать</span>
          </span>
        </div>
        <span className="tpl-preview__hero-media">
          {heroImage ? <img src={heroImage} alt="" /> : <Icon name="image" size={30} />}
        </span>
      </div>

      <div className="tpl-preview__products">
        {SAMPLE.map((item) => (
          <span className="tpl-preview__card" key={item.title}>
            <span className="tpl-preview__card-media">
              <Icon name={item.icon} size={22} />
            </span>
            <small>{item.title}</small>
            <strong>{formatMoney(item.price)}</strong>
          </span>
        ))}
      </div>

      <div className="tpl-preview__trust">
        <span>
          <Icon name="shield" size={14} /> Гарантия качества
        </span>
        <span>
          <Icon name="clock" size={14} /> Самовывоз сегодня
        </span>
        <span>
          <Icon name="phone" size={14} /> {phone || 'Связь с продавцом'}
        </span>
      </div>
    </div>
  )
}
