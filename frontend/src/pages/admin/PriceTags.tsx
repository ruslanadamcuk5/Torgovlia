import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { assetUrl } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useSite } from '../../store/SettingsContext'
import { useToast } from '../../store/ToastContext'
import { Loader } from '../../components/ui'
import { Icon } from '../../components/icons'
import type { Product } from '../../lib/types'
import { formatMoney, unitShort } from '../../lib/format'

const TEMPLATES = {
  price: { label: 'Ценник 100 × 70 мм', width: 100, height: 70, columns: 2, priceSize: 30 },
  a6: { label: 'Ценник A6, 148 × 105 мм', width: 148, height: 105, columns: 2, priceSize: 42 },
  label: { label: 'Этикетка 58 × 40 мм', width: 58, height: 40, columns: 4, priceSize: 16 },
} as const

type TemplateKey = keyof typeof TEMPLATES

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (char) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char] ?? char
  ))
}

function absolute(path: string) {
  const url = assetUrl(path)
  return /^https?:/i.test(url) ? url : new URL(url, window.location.origin).toString()
}

export default function PriceTags() {
  const { toast } = useToast()
  const { site } = useSite()
  const { data: features, loading: featuresLoading } = useApi<{ services: Record<string, boolean> }>('/admin/services/features')
  const enabled = Boolean(features?.services.price_tags)
  const { data, loading } = useApi<{ items: Product[]; total: number }>(enabled ? '/admin/products?limit=500' : null)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [template, setTemplate] = useState<TemplateKey>('price')
  const [copies, setCopies] = useState('1')
  const [showQr, setShowQr] = useState(true)
  const [showOldPrice, setShowOldPrice] = useState(true)
  const [showNote, setShowNote] = useState(true)
  const [showLegal, setShowLegal] = useState(true)

  const products = data?.items ?? []
  const visible = useMemo(() => {
    const term = query.trim().toLowerCase()
    if (!term) return products
    return products.filter((product) => `${product.title} ${product.category_title ?? ''}`.toLowerCase().includes(term))
  }, [products, query])

  const chosen = products.filter((product) => selected.has(product.id))
  const s = site?.settings

  const toggle = (id: number) => {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const selectVisible = () => {
    setSelected((current) => {
      const next = new Set(current)
      for (const product of visible) next.add(product.id)
      return next
    })
  }

  const print = () => {
    if (!chosen.length) {
      toast('Выберите хотя бы один товар', 'error')
      return
    }
    const config = TEMPLATES[template]
    const perProduct = Math.max(1, Math.min(20, Math.round(Number(copies) || 1)))
    const rows = chosen.flatMap((product) => Array.from({ length: perProduct }, () => product))
    const win = window.open('', '_blank', 'width=1000,height=800')
    if (!win) {
      toast('Разрешите всплывающие окна, чтобы напечатать ценники', 'error')
      return
    }

    const tags = rows.map((product) => {
      const hasDiscount = product.discount_percent > 0
      const note = product.weight_note || product.subtitle || product.short_description
      const qr = showQr
        ? `<img class="tag__qr" src="${absolute(`/api/qr/product/${product.slug}.png?size=320`)}" alt="QR ${escapeHtml(product.title)}" />`
        : ''
      return `<article class="tag">
        <div class="tag__brand">${escapeHtml(s?.brand_name ?? '')}</div>
        <div class="tag__main">
          <h2>${escapeHtml(product.title)}</h2>
          ${showNote && note ? `<p class="tag__note">${escapeHtml(note)}</p>` : ''}
          <div class="tag__prices">
            <strong class="tag__price">${formatMoney(product.final_price)}</strong>
            <span class="tag__unit">за ${unitShort(product.unit)}</span>
            ${showOldPrice && hasDiscount ? `<del>${formatMoney(product.price)}</del><b class="tag__sale">−${product.discount_percent}%</b>` : ''}
          </div>
        </div>
        ${qr}
        ${showLegal && s ? `<footer>${escapeHtml(s.legal_name)}${s.unp ? ` · УНП ${escapeHtml(s.unp)}` : ''}</footer>` : ''}
      </article>`
    }).join('')

    const columns = config.columns
    win.document.write(`<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Ценники — ${escapeHtml(s?.brand_name ?? '')}</title>
      <style>
        *{box-sizing:border-box} body{font-family:'Segoe UI',Arial,sans-serif;margin:8mm;color:#08272e}
        .tags{display:grid;grid-template-columns:repeat(${columns},${config.width}mm);gap:4mm;justify-content:start}
        .tag{width:${config.width}mm;height:${config.height}mm;border:1px dashed #c9d4d1;border-radius:3mm;padding:4mm;display:flex;flex-direction:column;justify-content:space-between;break-inside:avoid;overflow:hidden}
        .tag__brand{font-size:2.6mm;letter-spacing:.08em;text-transform:uppercase;color:#52706f;font-weight:700}
        .tag__main{display:flex;flex-direction:column;gap:1.2mm;min-height:0}
        .tag h2{font-size:${config.priceSize > 20 ? 5 : 3.2}mm;line-height:1.15;margin:0}
        .tag__note{font-size:2.6mm;line-height:1.25;color:#52706f;margin:0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
        .tag__prices{display:flex;align-items:baseline;gap:2mm;flex-wrap:wrap}
        .tag__price{font-size:${config.priceSize / 3}mm;line-height:1;letter-spacing:-.02em}
        .tag__unit{font-size:2.6mm;color:#52706f}
        .tag del{font-size:2.6mm;color:#8a9b98}
        .tag__sale{font-size:2.6mm;color:#fff;background:#b2423d;border-radius:2mm;padding:.5mm 1.2mm}
        .tag__qr{width:${config.priceSize > 20 ? 22 : 13}mm;height:${config.priceSize > 20 ? 22 : 13}mm;align-self:flex-end}
        .tag footer{font-size:2mm;line-height:1.2;color:#6b807e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        @page{size:A4;margin:8mm}
        @media print{.tag{border-color:#eee}}
      </style></head><body>
      <div class="tags">${tags}</div>
      <script>window.onload=()=>{setTimeout(()=>window.print(),400)}</script>
      </body></html>`)
    win.document.close()
  }

  if (featuresLoading) return <Loader />

  if (!enabled) {
    return (
      <div className="admin-page">
        <section className="panel panel--accent">
          <div className="panel__head"><h2>Ценники и этикетки</h2></div>
          <p>
            Печать ценников доступна на тарифе <strong>«Бизнес»</strong> и выше.
            Включите сервис в разделе «Сервисы» — после этого здесь появится печать.
          </p>
          <Link to="/admin/services" className="btn btn--primary">Перейти к сервисам <Icon name="arrow-right" size={17} /></Link>
        </section>
      </div>
    )
  }

  if (loading) return <Loader />

  return (
    <div className="admin-page price-tags-page">
      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Печать ценников</h2>
            <p className="muted">
              Выберите товары и размер. В ценник попадут название, цена, старая цена со скидкой,
              короткое описание, QR на статью и реквизиты магазина.
            </p>
          </div>
          <span className="muted">{chosen.length} выбрано</span>
        </div>

        <div className="price-tags-controls">
          <label className="field">
            <span className="field__label">Размер</span>
            <select className="input input--select" value={template} onChange={(event) => setTemplate(event.target.value as TemplateKey)}>
              {(Object.keys(TEMPLATES) as TemplateKey[]).map((key) => (
                <option key={key} value={key}>{TEMPLATES[key].label}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field__label">Копий каждого</span>
            <input className="input" type="number" min="1" max="20" value={copies} onChange={(event) => setCopies(event.target.value)} />
          </label>
          <div className="price-tags-switches">
            <label className="checkbox"><input type="checkbox" checked={showQr} onChange={(event) => setShowQr(event.target.checked)} /><span>QR-код</span></label>
            <label className="checkbox"><input type="checkbox" checked={showOldPrice} onChange={(event) => setShowOldPrice(event.target.checked)} /><span>Старая цена и скидка</span></label>
            <label className="checkbox"><input type="checkbox" checked={showNote} onChange={(event) => setShowNote(event.target.checked)} /><span>Описание</span></label>
            <label className="checkbox"><input type="checkbox" checked={showLegal} onChange={(event) => setShowLegal(event.target.checked)} /><span>Реквизиты</span></label>
          </div>
        </div>

        <div className="price-tags-actions">
          <button type="button" className="btn btn--primary" onClick={print} disabled={!chosen.length}>
            <Icon name="print" size={18} /> Печать · {chosen.length * Math.max(1, Number(copies) || 1)} шт.
          </button>
          <span className="muted">Печать откроется в новом окне. В диалоге выберите A4 и поля 8 мм.</span>
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <h2>Товары</h2>
          <div className="price-tags-tools">
            <label className="search-field">
              <Icon name="search" size={16} />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Название или категория" type="search" />
            </label>
            <button type="button" className="btn btn--sm btn--ghost" onClick={selectVisible}>Выбрать найденные</button>
            <button type="button" className="btn btn--sm btn--ghost" onClick={() => setSelected(new Set())}>Сбросить</button>
          </div>
        </div>

        <div className="price-tags-list">
          {visible.map((product) => (
            <label key={product.id} className={`price-tag-row ${selected.has(product.id) ? 'is-selected' : ''}`}>
              <input type="checkbox" checked={selected.has(product.id)} onChange={() => toggle(product.id)} />
              <span className="price-tag-row__title">
                <strong>{product.title}</strong>
                <small>{product.category_title ?? 'Без категории'} · цена за {unitShort(product.unit)}</small>
              </span>
              <span className="price-tag-row__price">
                <strong>{formatMoney(product.final_price)}</strong>
                {product.discount_percent > 0 && <del>{formatMoney(product.price)}</del>}
              </span>
            </label>
          ))}
        </div>
        {visible.length === 0 && <p className="muted">Товары не найдены.</p>}
      </section>
    </div>
  )
}
