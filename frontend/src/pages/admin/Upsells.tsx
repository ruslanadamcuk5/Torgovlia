import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Loader, Spinner } from '../../components/ui'
import { Icon } from '../../components/icons'
import { formatMoney } from '../../lib/format'

interface ProductLite {
  id: number
  title: string
  price: number
  category_title?: string | null
  barcode?: string | null
}

interface UpsellRule {
  id: number
  product_id: number
  product_title: string
  product_slug: string
  items: { id: number; title: string; price: number }[]
  is_active: boolean
  updated_at: string
}

export default function Upsells() {
  const { toast } = useToast()
  const { data: features, loading: featuresLoading } = useApi<{ services: Record<string, boolean> }>(
    '/admin/services/features',
  )
  const enabled = Boolean(features?.services.upsell)
  const { data: productsData } = useApi<{ items: ProductLite[] }>(enabled ? '/admin/products?limit=1000' : null)
  const { data: rulesData, reload } = useApi<{ items: UpsellRule[] }>(enabled ? '/admin/upsells' : null)

  const [productId, setProductId] = useState('')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<number[]>([])
  const [saving, setSaving] = useState(false)

  const products = useMemo(
    () => (productsData?.items ?? []).filter((item) => item.id),
    [productsData],
  )
  const current = products.find((item) => String(item.id) === productId) ?? null
  const rules = rulesData?.items ?? []

  useEffect(() => {
    if (!productId) {
      setSelected([])
      return
    }
    const rule = rules.find((item) => item.product_id === Number(productId))
    setSelected(rule ? rule.items.map((item) => item.id) : [])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId, rulesData])

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    return products
      .filter((item) => item.id !== Number(productId))
      .filter((item) => !selected.includes(item.id))
      .filter((item) => !query || item.title.toLowerCase().includes(query) || (item.barcode ?? '').includes(query))
      .slice(0, 40)
  }, [products, productId, selected, search])

  const toggle = (id: number) => {
    setSelected((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : current.length >= 8 ? current : [...current, id],
    )
  }

  const save = async () => {
    if (!current) {
      toast('Выберите товар, для которого настраиваем рекомендации', 'error')
      return
    }
    setSaving(true)
    try {
      await api(`/admin/upsells/${current.id}`, {
        method: 'PUT',
        body: { items: selected, is_active: true },
      })
      reload()
      toast(selected.length ? 'Рекомендации сохранены' : 'Рекомендации очищены')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить', 'error')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (rule: UpsellRule) => {
    if (!window.confirm(`Удалить рекомендации для「${rule.product_title}」?`)) return
    try {
      await api(`/admin/upsells/${rule.product_id}`, { method: 'DELETE' })
      if (rule.product_id === Number(productId)) setSelected([])
      reload()
      toast('Рекомендации удалены')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось удалить', 'error')
    }
  }

  const editRule = (rule: UpsellRule) => {
    setProductId(String(rule.product_id))
    setSearch('')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  if (featuresLoading) return <Loader />

  if (!enabled) {
    return (
      <div className="admin-page">
        <section className="panel panel--accent">
          <div className="panel__head"><h2>Допродажи</h2></div>
          <p>
            Рекомендации «с этим покупают» доступны на тарифе <strong>«Про»</strong>.
            Выберите товары, которые показывать в карточке вместе с основным.
          </p>
          <Link to="/admin/services" className="btn btn--primary">
            Перейти к сервисам <Icon name="arrow-right" size={17} />
          </Link>
        </section>
      </div>
    )
  }

  return (
    <div className="admin-page upsells-page">
      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Допродажи</h2>
            <p className="muted">
              Ручные рекомендации показываются на карточке товара в блоке «С этим покупают».
              До восьми товаров на позицию; остальные места добираются из той же категории.
            </p>
          </div>
        </div>

        <div className="upsell-picker">
          <label className="field">
            <span className="field__label">Основной товар</span>
            <select
              className="input input--select"
              value={productId}
              onChange={(event) => {
                setProductId(event.target.value)
                setSearch('')
              }}
            >
              <option value="">Выберите товар</option>
              {products.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title}
                </option>
              ))}
            </select>
          </label>
          {current && (
            <div className="upsell-current">
              <span className="muted">Рекомендуем к</span>
              <strong>{current.title}</strong>
              <span className="muted">{formatMoney(current.price)}</span>
            </div>
          )}
        </div>

        {current && (
          <>
            <div className="upsell-selected">
              {selected.length === 0 && <span className="muted">Пока ничего не выбрано — покажем товары из той же категории.</span>}
              {selected.map((id) => {
                const item = products.find((row) => row.id === id)
                return (
                  <button type="button" key={id} className="upsell-chip" onClick={() => toggle(id)}>
                    {item?.title ?? `Товар #${id}`}
                    <Icon name="close" size={13} />
                  </button>
                )
              })}
            </div>

            <div className="upsell-search">
              <Icon name="search" size={16} />
              <input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Найти товар по названию или штрихкоду"
                maxLength={80}
              />
              <span className="muted">{selected.length} / 8</span>
            </div>

            <div className="upsell-grid">
              {filtered.map((item) => (
                <button type="button" key={item.id} className="upsell-card" onClick={() => toggle(item.id)}>
                  <span className="upsell-card__title">{item.title}</span>
                  <span className="upsell-card__meta">
                    {item.category_title ?? 'Без категории'} · {formatMoney(item.price)}
                  </span>
                  <span className="upsell-card__add">+ Добавить</span>
                </button>
              ))}
              {filtered.length === 0 && <p className="muted">Ничего не нашлось.</p>}
            </div>

            <div className="upsell-actions">
              <button type="button" className="btn btn--primary" onClick={save} disabled={saving}>
                {saving ? <Spinner /> : <Icon name="check" size={16} />} Сохранить рекомендации
              </button>
              <span className="muted">Изменения появятся на витрине сразу.</span>
            </div>
          </>
        )}
      </section>

      <section className="panel">
        <div className="panel__head">
          <h3>Настроенные рекомендации</h3>
          <span className="muted">{rules.length}</span>
        </div>
        <div className="upsell-rules">
          {rules.map((rule) => (
            <div className={`upsell-rule${rule.is_active ? '' : ' is-off'}`} key={rule.id}>
              <div className="upsell-rule__main">
                <strong>{rule.product_title}</strong>
                <small>
                  {rule.items.length
                    ? rule.items.map((item) => item.title).join(', ')
                    : 'Без ручных рекомендаций — из категории'}
                </small>
              </div>
              <span className="muted">{new Date(rule.updated_at).toLocaleDateString('ru-BY')}</span>
              <div className="upsell-rule__actions">
                <button type="button" className="btn btn--sm btn--ghost" onClick={() => editRule(rule)}>
                  Изменить
                </button>
                <button type="button" className="btn btn--sm btn--ghost" onClick={() => remove(rule)}>
                  Удалить
                </button>
              </div>
            </div>
          ))}
          {rules.length === 0 && (
            <p className="muted">
              Пока нет ручных рекомендаций. Витрина показывает похожие товары из категории автоматически.
            </p>
          )}
        </div>
      </section>
    </div>
  )
}
