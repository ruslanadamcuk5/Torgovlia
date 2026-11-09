import { useMemo, useState } from 'react'
import { api, assetUrl } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Loader, Spinner } from '../../components/ui'
import { Icon } from '../../components/icons'
import type { Product } from '../../lib/types'
import { formatMoney, unitShort } from '../../lib/format'

export default function Promotions() {
  const { toast } = useToast()
  const { data, loading, reload } = useApi<{ items: Product[]; total: number }>('/admin/products?limit=500')
  const [discounts, setDiscounts] = useState<Record<number, string>>({})
  const [busyId, setBusyId] = useState<number | null>(null)
  const [query, setQuery] = useState('')

  const products = data?.items ?? []
  const daily = products.find((product) => product.is_daily_deal)
  const discounted = products.filter((product) => product.discount_percent > 0 && !product.is_daily_deal)
  const visible = useMemo(() => {
    const term = query.trim().toLowerCase()
    if (!term) return products
    return products.filter((product) => `${product.title} ${product.category_title ?? ''}`.toLowerCase().includes(term))
  }, [products, query])

  const setDaily = async (product: Product) => {
    if (product.is_daily_deal) {
      setBusyId(product.id)
      try {
        await api(`/admin/products/${product.id}`, { method: 'PATCH', body: { is_daily_deal: false } })
        toast('Товар дня снят')
        reload()
      } catch (err) {
        toast(err instanceof Error ? err.message : 'Не удалось обновить товар дня', 'error')
      } finally {
        setBusyId(null)
      }
      return
    }

    setBusyId(product.id)
    try {
      if (daily) {
        await api(`/admin/products/${daily.id}`, { method: 'PATCH', body: { is_daily_deal: false } })
      }
      await api(`/admin/products/${product.id}`, { method: 'PATCH', body: { is_daily_deal: true } })
      toast(`«${product.title}» — товар дня`)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось назначить товар дня', 'error')
    } finally {
      setBusyId(null)
    }
  }

  const saveDiscount = async (product: Product) => {
    const raw = discounts[product.id] ?? String(product.discount_percent)
    const value = Math.max(0, Math.min(95, Number(raw) || 0))
    setBusyId(product.id)
    try {
      await api(`/admin/products/${product.id}`, { method: 'PATCH', body: { discount_percent: value } })
      toast(value > 0 ? `Скидка ${value}% на «${product.title}»` : 'Скидка снята')
      setDiscounts((current) => {
        const next = { ...current }
        delete next[product.id]
        return next
      })
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить скидку', 'error')
    } finally {
      setBusyId(null)
    }
  }

  if (loading) return <Loader />

  return (
    <div className="admin-page">
      <div className="promo-summary">
        <article className="promo-summary__card promo-summary__card--daily">
          <span className="promo-summary__icon"><Icon name="star" size={22} /></span>
          <div>
            <span>Товар дня</span>
            <strong>{daily?.title ?? 'Не выбран'}</strong>
            <small>{daily ? `${formatMoney(daily.final_price)} / ${unitShort(daily.unit)}` : 'Выберите товар в таблице ниже'}</small>
          </div>
        </article>
        <article className="promo-summary__card">
          <span className="promo-summary__icon"><Icon name="percent" size={22} /></span>
          <div>
            <span>Товаров со скидкой</span>
            <strong>{discounted.length}</strong>
            <small>Скидки показываются в каталоге и на главной</small>
          </div>
        </article>
        <article className="promo-summary__card">
          <span className="promo-summary__icon"><Icon name="tag" size={22} /></span>
          <div>
            <span>Активных товаров</span>
            <strong>{products.filter((product) => product.is_active).length}</strong>
            <small>из {products.length} в каталоге</small>
          </div>
        </article>
      </div>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Скидки и товар дня</h2>
            <p className="muted">Скидка применяется к цене в каталоге. Товар дня дополнительно выделяется на главной.</p>
          </div>
          <label className="search-field">
            <Icon name="search" size={17} />
            <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Найти товар" />
          </label>
        </div>

        <div className="table-wrap">
          <table className="data-table data-table--promo">
            <thead>
              <tr>
                <th>Товар</th>
                <th>Базовая цена</th>
                <th>Скидка</th>
                <th>Цена для покупателя</th>
                <th>Товар дня</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {visible.map((product) => {
                const value = discounts[product.id] ?? String(product.discount_percent)
                const preview = Math.round(product.price * (100 - (Number(value) || 0)) / 100 * 100) / 100
                return (
                  <tr key={product.id}>
                    <td>
                      <div className="table-product">
                        <span className="table-product__img">
                          {product.image_url ? <img src={assetUrl(product.image_url)} alt="" /> : <Icon name="image" size={20} />}
                        </span>
                        <div>
                          <strong>{product.title}</strong>
                          <span className="table-sub">{product.category_title ?? 'Без категории'} {!product.is_active && '· скрыт'}</span>
                        </div>
                      </div>
                    </td>
                    <td>{formatMoney(product.price)}</td>
                    <td>
                      <span className="discount-input">
                        <input
                          className="input input--sm"
                          type="number"
                          min="0"
                          max="95"
                          value={value}
                          onChange={(event) => setDiscounts((current) => ({ ...current, [product.id]: event.target.value }))}
                        />
                        <span>%</span>
                      </span>
                    </td>
                    <td>
                      <strong>{formatMoney(preview)}</strong>
                      {Number(value) > 0 && <span className="table-sub">/ {unitShort(product.unit)}</span>}
                    </td>
                    <td>
                      <button
                        type="button"
                        className={`star-toggle ${product.is_daily_deal ? 'is-active' : ''}`}
                        onClick={() => void setDaily(product)}
                        disabled={busyId === product.id}
                        title={product.is_daily_deal ? 'Снять товар дня' : 'Назначить товаром дня'}
                      >
                        {busyId === product.id ? <Spinner size={16} /> : <Icon name="star" size={18} />}
                      </button>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn btn--sm btn--outline"
                        onClick={() => void saveDiscount(product)}
                        disabled={busyId === product.id || Number(value) === product.discount_percent}
                      >
                        Сохранить
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {visible.length === 0 && <p className="muted">Товары не найдены.</p>}
      </section>

      <div className="notice notice--info">
        <Icon name="info" size={18} />
        <span>
          Скидка не является публичной офертой и действует на момент оформления заказа. При изменении цены уже созданные
          заказы сохраняют стоимость, зафиксированную при оформлении.
        </span>
      </div>
    </div>
  )
}
