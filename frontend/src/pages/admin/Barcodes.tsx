import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useSite } from '../../store/SettingsContext'
import { useToast } from '../../store/ToastContext'
import { Loader, Spinner } from '../../components/ui'
import { Barcode } from '../../components/Barcode'
import { Icon } from '../../components/icons'
import { ean13Bars, ean13Digits, isValidEan13 } from '../../lib/barcode'
import { formatMoney, unitShort } from '../../lib/format'
import type { Product } from '../../lib/types'

const LABEL_COLUMNS = 3
const COPIES_LIMIT = 30

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (char) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char] ?? char
  ))
}

function barcodeMarkup(code?: string | null) {
  if (!code || !isValidEan13(code)) return ''
  const bars = ean13Bars(code)
  const rects = bars
    .map((bar) => `<rect x="${bar.x}" y="0" width="${bar.width}" height="88" />`)
    .join('')
  const [prefix, left, right] = ean13Digits(code)
  return `<div class="label__barcode">
    <svg viewBox="0 0 95 88" preserveAspectRatio="none">${rects}</svg>
    <div class="label__digits"><span>${prefix}</span><span>${left}</span><span>${right}</span></div>
  </div>`
}

export default function Barcodes() {
  const { toast } = useToast()
  const { site } = useSite()
  const { data: features, loading: featuresLoading } = useApi<{ services: Record<string, boolean> }>('/admin/services/features')
  const barcodeEnabled = Boolean(features?.services.barcode)
  const labelsEnabled = Boolean(features?.services.labels)
  const enabled = barcodeEnabled || labelsEnabled

  const { data, loading, reload } = useApi<{ items: Product[]; total: number }>(enabled ? '/admin/products?limit=1000' : null)
  const [query, setQuery] = useState('')
  const [scan, setScan] = useState('')
  const [scanning, setScanning] = useState(false)
  const [found, setFound] = useState<Product | null>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [copies, setCopies] = useState('1')
  const [busy, setBusy] = useState<number | 'backfill' | null>(null)
  const scanRef = useRef<HTMLInputElement>(null)

  const products = data?.items ?? []
  const visible = useMemo(() => {
    const term = query.trim().toLowerCase()
    if (!term) return products
    return products.filter((product) => (
      `${product.title} ${product.barcode ?? ''} ${product.category_title ?? ''}`.toLowerCase().includes(term)
    ))
  }, [products, query])

  const chosen = products.filter((product) => selected.has(product.id))
  const missing = products.filter((product) => !isValidEan13(product.barcode)).length
  const s = site?.settings

  useEffect(() => {
    scanRef.current?.focus()
  }, [enabled, loading])

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

  const lookup = async () => {
    const code = scan.trim()
    if (!code) return
    setScanning(true)
    try {
      const product = await api<Product>(`/admin/barcodes/lookup?code=${encodeURIComponent(code)}`)
      setFound(product)
      setSelected((current) => new Set(current).add(product.id))
      setQuery('')
      setScan('')
      toast(`Найдено: ${product.title}`)
    } catch (err) {
      setFound(null)
      toast(err instanceof Error ? err.message : 'Товар не найден', 'error')
    } finally {
      setScanning(false)
      scanRef.current?.focus()
    }
  }

  const generateOne = async (product: Product) => {
    setBusy(product.id)
    try {
      const updated = await api<Product>(`/admin/products/${product.id}/barcode`, { method: 'POST' })
      toast(`Штрихкод ${updated.barcode} создан`)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось создать штрихкод', 'error')
    } finally {
      setBusy(null)
    }
  }

  const backfill = async () => {
    setBusy('backfill')
    try {
      const result = await api<{ updated: number }>('/admin/barcodes/backfill', { method: 'POST' })
      toast(result.updated ? `Создано кодов: ${result.updated}` : 'У всех товаров уже есть коды')
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось создать коды', 'error')
    } finally {
      setBusy(null)
    }
  }

  const print = () => {
    if (!labelsEnabled) {
      toast('Печать этикеток не включена в тарифах магазина', 'error')
      return
    }
    if (!chosen.length) {
      toast('Выберите хотя бы один товар', 'error')
      return
    }
    const perProduct = Math.max(1, Math.min(COPIES_LIMIT, Math.round(Number(copies) || 1)))
    const rows = chosen.flatMap((product) => Array.from({ length: perProduct }, () => product))
    const win = window.open('', '_blank', 'width=1000,height=800')
    if (!win) {
      toast('Разрешите всплывающие окна, чтобы напечатать этикетки', 'error')
      return
    }

    const labels = rows.map((product) => `<article class="label">
      <div class="label__brand">${escapeHtml(s?.brand_name ?? '')}</div>
      <div class="label__title">${escapeHtml(product.title)}</div>
      <div class="label__price">${escapeHtml(formatMoney(product.final_price))}</div>
      ${barcodeMarkup(product.barcode)}
      <div class="label__legal">${escapeHtml(s?.legal_name ?? '')}${s?.unp ? ` · УНП ${escapeHtml(s.unp)}` : ''}</div>
    </article>`).join('')

    win.document.write(`<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Этикетки — ${escapeHtml(s?.brand_name ?? '')}</title>
      <style>
        *{box-sizing:border-box} body{font-family:'Segoe UI',Arial,sans-serif;margin:8mm;color:#08272e}
        .labels{display:grid;grid-template-columns:repeat(${LABEL_COLUMNS},58mm);gap:4mm;justify-content:start}
        .label{width:58mm;height:40mm;border:1px dashed #c9d4d1;border-radius:2mm;padding:3mm 3.2mm;display:flex;flex-direction:column;break-inside:avoid;overflow:hidden}
        .label__brand{font-size:2mm;letter-spacing:.08em;text-transform:uppercase;color:#52706f;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .label__title{font-size:3.1mm;font-weight:700;line-height:1.14;margin-top:.8mm;max-height:7.2mm;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
        .label__price{font-size:5.6mm;font-weight:800;line-height:1;margin-top:1mm;letter-spacing:-.02em;white-space:nowrap}
        .label__barcode{margin-top:auto}
        .label__barcode svg{display:block;width:100%;height:8.4mm}
        .label__digits{display:flex;justify-content:space-between;font-size:2mm;letter-spacing:.12em;margin-top:.4mm;font-variant-numeric:tabular-nums}
        .label__legal{font-size:1.55mm;line-height:1.2;color:#6b807e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:.6mm}
        @page{size:A4;margin:8mm}
        @media print{.label{border-color:#eee}}
      </style></head><body>
      <div class="labels">${labels}</div>
      <script>window.onload=()=>{setTimeout(()=>window.print(),400)}</script>
      </body></html>`)
    win.document.close()
  }

  if (featuresLoading) return <Loader />

  if (!enabled) {
    return (
      <div className="admin-page">
        <section className="panel panel--accent">
          <div className="panel__head"><h2>Штрихкоды и этикетки</h2></div>
          <p>
            Сканирование и печать этикеток доступны на тарифе <strong>«Бизнес»</strong> и выше.
            Включите сервисы «Штрихкоды» и «Печать этикеток» в разделе «Сервисы».
          </p>
          <Link to="/admin/services" className="btn btn--primary">Перейти к сервисам <Icon name="arrow-right" size={17} /></Link>
        </section>
      </div>
    )
  }

  if (loading) return <Loader label="Загружаем товары…" />

  return (
    <div className="admin-page barcodes-page">
      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Штрихкоды и этикетки</h2>
            <p className="muted">
              Сканер вводит код как текст и нажимает Enter. Коды EAN-13 создаются автоматически,
              этикетка 58 × 40 мм печатается на A4.
            </p>
          </div>
          {missing > 0 && (
            <button type="button" className="btn btn--outline" onClick={backfill} disabled={busy === 'backfill'}>
              {busy === 'backfill' ? <Spinner /> : <Icon name="tag" size={16} />} Создать коды · {missing}
            </button>
          )}
        </div>

        <div className="barcode-scan">
          <label className="field">
            <span className="field__label">Поиск по сканеру или коду</span>
            <div className="barcode-scan__input">
              <Icon name="search" size={17} />
              <input
                ref={scanRef}
                className="input"
                value={scan}
                onChange={(event) => setScan(event.target.value.replace(/[^\d]/g, '').slice(0, 13))}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault()
                    void lookup()
                  }
                }}
                inputMode="numeric"
                placeholder="Наведите сканер или введите 13 цифр"
                disabled={!barcodeEnabled || scanning}
              />
              <button type="button" className="btn btn--primary" onClick={lookup} disabled={!barcodeEnabled || scanning || !scan.trim()}>
                {scanning ? <Spinner /> : <Icon name="search" size={16} />} Найти
              </button>
            </div>
          </label>
          {!barcodeEnabled && <p className="muted">Сервис «Штрихкоды» отключён — поиск по сканеру недоступен.</p>}
          {found && (
            <div className="barcode-found">
              <Barcode code={found.barcode} height={38} />
              <div>
                <strong>{found.title}</strong>
                <small>{formatMoney(found.final_price)} · за {unitShort(found.unit)}</small>
              </div>
              <span className="barcode-found__code">{found.barcode}</span>
            </div>
          )}
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h3>Этикетки 58 × 40 мм</h3>
            <p className="muted">{chosen.length} выбрано · {products.length} товаров</p>
          </div>
          <div className="barcode-actions">
            <label className="field barcode-copies">
              <span className="field__label">Копий каждого</span>
              <input className="input" type="number" min="1" max={COPIES_LIMIT} value={copies} onChange={(event) => setCopies(event.target.value)} />
            </label>
            <button type="button" className="btn btn--primary" onClick={print} disabled={!labelsEnabled || !chosen.length}>
              <Icon name="print" size={18} /> Печать · {chosen.length * Math.max(1, Number(copies) || 1)} шт.
            </button>
          </div>
        </div>

        <div className="barcode-preview">
          {chosen.slice(0, 4).map((product) => (
            <article className="label-preview" key={product.id}>
              <div className="label-preview__brand">{s?.brand_name}</div>
              <div className="label-preview__title">{product.title}</div>
              <div className="label-preview__price">{formatMoney(product.final_price)}</div>
              <Barcode code={product.barcode} height={34} />
              <div className="label-preview__legal">
                {s?.legal_name}{s?.unp ? ` · УНП ${s.unp}` : ''}
              </div>
            </article>
          ))}
          {chosen.length === 0 && (
            <p className="muted">Выберите товары ниже — здесь появится превью этикеток.</p>
          )}
        </div>
        {chosen.length > 4 && <p className="muted">Показаны первые 4 из {chosen.length} этикеток.</p>}
        {!labelsEnabled && <p className="muted">Сервис «Печать этикеток» отключён — печать недоступна.</p>}
      </section>

      <section className="panel">
        <div className="panel__head">
          <h3>Товары</h3>
          <div className="barcode-tools">
            <label className="search-field">
              <Icon name="search" size={16} />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Название, код или категория" type="search" />
            </label>
            <button type="button" className="btn btn--sm btn--ghost" onClick={selectVisible}>Выбрать найденные</button>
            <button type="button" className="btn btn--sm btn--ghost" onClick={() => setSelected(new Set())}>Сбросить</button>
          </div>
        </div>

        <div className="barcode-list">
          {visible.map((product) => (
            <div className={`barcode-row ${selected.has(product.id) ? 'is-selected' : ''}`} key={product.id}>
              <label className="barcode-row__check">
                <input type="checkbox" checked={selected.has(product.id)} onChange={() => toggle(product.id)} />
              </label>
              <div className="barcode-row__main">
                <strong>{product.title}</strong>
                <small>{product.category_title ?? 'Без категории'} · {formatMoney(product.final_price)}</small>
              </div>
              <div className="barcode-row__code">
                {product.barcode ? (
                  <>
                    <Barcode code={product.barcode} height={26} />
                    <span>{product.barcode}</span>
                  </>
                ) : (
                  <span className="barcode-row__empty">Код не создан</span>
                )}
              </div>
              {!product.barcode && (
                <button
                  type="button"
                  className="btn btn--sm btn--ghost"
                  onClick={() => generateOne(product)}
                  disabled={busy === product.id}
                >
                  {busy === product.id ? <Spinner /> : <Icon name="tag" size={14} />} Создать
                </button>
              )}
            </div>
          ))}
          {visible.length === 0 && <p className="muted">Товары не найдены.</p>}
        </div>
      </section>
    </div>
  )
}
