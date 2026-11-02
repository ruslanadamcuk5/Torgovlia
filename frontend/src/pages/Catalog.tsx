import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useSite } from '../store/SettingsContext'
import { useApi } from '../lib/useApi'
import { useDebounced } from '../components/ui'
import { ProductCard } from '../components/ProductCard'
import { Icon } from '../components/icons'
import type { Category, Product } from '../lib/types'

const SORTS = [
  { value: 'default', label: 'По популярности' },
  { value: 'price_asc', label: 'Сначала дешевле' },
  { value: 'price_desc', label: 'Сначала дороже' },
  { value: 'new', label: 'Новинки' },
  { value: 'title', label: 'По названию' },
]

export default function Catalog() {
  const { site } = useSite()
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState(params.get('q') ?? '')
  const debouncedQuery = useDebounced(query, 350)
  const [sort, setSort] = useState('default')
  const [availableOnly, setAvailableOnly] = useState(false)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const category = params.get('category') ?? ''

  const { data: categories } = useApi<Category[]>('/categories', false)
  const path = useMemo(() => {
    const search = new URLSearchParams({ limit: '100', sort })
    if (category) search.set('category', category)
    if (debouncedQuery.trim()) search.set('q', debouncedQuery.trim())
    if (availableOnly) search.set('available_only', 'true')
    return `/products?${search.toString()}`
  }, [category, debouncedQuery, sort, availableOnly])

  const { data, loading } = useApi<{ items: Product[]; total: number }>(path, false)

  const setCategory = (slug: string) => {
    const next = new URLSearchParams(params)
    if (slug) next.set('category', slug)
    else next.delete('category')
    setParams(next, { replace: true })
    setFiltersOpen(false)
  }

  const activeCategory = categories?.find((item) => item.slug === category)

  if (!site) return null
  const s = site.settings

  return (
    <div className="catalog-page">
      <div className="page-head">
        <div className="container">
          <div className="breadcrumbs">
            <span>Главная</span><Icon name="chevron-right" size={13} /><span>Каталог</span>
            {activeCategory && <><Icon name="chevron-right" size={13} /><span>{activeCategory.title}</span></>}
          </div>
          <div className="page-head__row">
            <div>
              <span className="eyebrow">Свежесть каждый день</span>
              <h1>Каталог рыбы и морепродуктов</h1>
              <p className="page-head__sub">
                {s.city}, {s.market_name}, {s.pavilion} · самовывоз, оплата при получении
              </p>
            </div>
            <div className="page-head__badge">
              <Icon name="shield" size={20} />
              <span>Документы на каждую партию</span>
            </div>
          </div>
        </div>
      </div>

      <div className="container catalog-layout">
        <aside className={`filters ${filtersOpen ? 'is-open' : ''}`}>
          <div className="filters__mobile-head">
            <strong>Фильтры</strong>
            <button type="button" className="icon-btn" onClick={() => setFiltersOpen(false)} aria-label="Закрыть">
              <Icon name="close" size={20} />
            </button>
          </div>

          <div className="filters__block">
            <h3>Поиск</h3>
            <label className="search-field">
              <Icon name="search" size={18} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Сельдь, форель, креветки…"
                type="search"
              />
            </label>
          </div>

          <div className="filters__block">
            <h3>Категории</h3>
            <div className="filters__list">
              <button type="button" className={!category ? 'is-active' : ''} onClick={() => setCategory('')}>
                <span>Все товары</span>
                <b>{categories?.reduce((sum, item) => sum + item.products_count, 0) ?? ''}</b>
              </button>
              {categories?.map((item) => (
                <button
                  key={item.slug}
                  type="button"
                  className={category === item.slug ? 'is-active' : ''}
                  onClick={() => setCategory(item.slug)}
                >
                  <span>{item.title}</span>
                  <b>{item.products_count}</b>
                </button>
              ))}
            </div>
          </div>

          <div className="filters__block">
            <h3>Наличие</h3>
            <label className="switch-row">
              <span>Только в наличии</span>
              <input type="checkbox" checked={availableOnly} onChange={(event) => setAvailableOnly(event.target.checked)} />
              <span className="switch" />
            </label>
            <p className="filters__hint">Товары, которых сегодня нет, отмечены в каталоге. Их можно посмотреть и забронировать позже.</p>
          </div>

          <div className="filters__block filters__block--info">
            <span className="filters__info-icon"><Icon name="info" size={20} /></span>
            <div>
              <strong>Нужна помощь?</strong>
              <p>Позвоните — подскажем, что свежее сегодня.</p>
              <a href={`tel:${s.phone.replace(/[^\d+]/g, '')}`}>{s.phone}</a>
            </div>
          </div>
        </aside>

        <div className="catalog-main">
          <div className="catalog-toolbar">
            <button type="button" className="btn btn--outline btn--sm catalog-toolbar__filter" onClick={() => setFiltersOpen(true)}>
              <Icon name="filter" size={17} /> Фильтры
            </button>
            <span className="catalog-toolbar__count">
              {loading ? 'Ищем…' : `${data?.total ?? 0} ${data?.total === 1 ? 'товар' : 'товаров'}`}
            </span>
            <label className="select-inline">
              <span>Сортировка</span>
              <select value={sort} onChange={(event) => setSort(event.target.value)}>
                {SORTS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
          </div>

          {loading ? (
            <div className="product-grid">
              {Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="product-skeleton">
                  <span className="skeleton skeleton--media" />
                  <span className="skeleton skeleton--line" />
                  <span className="skeleton skeleton--line skeleton--short" />
                </div>
              ))}
            </div>
          ) : data && data.items.length > 0 ? (
            <div className="product-grid">
              {data.items.map((product) => <ProductCard key={product.id} product={product} />)}
            </div>
          ) : (
            <div className="empty-state empty-state--catalog">
              <span className="empty-state__icon"><Icon name="search" size={30} /></span>
              <h3>Ничего не нашлось</h3>
              <p>Измените запрос или снимите фильтр наличия. Ассортимент обновляется каждый день.</p>
              <button type="button" className="btn btn--primary" onClick={() => { setQuery(''); setCategory(''); setAvailableOnly(false) }}>
                Сбросить фильтры
              </button>
            </div>
          )}

          <div className="catalog-note">
            <Icon name="info" size={20} />
            <p>
              Весовой товар рассчитывается по фактическому весу при выдаче. Цены указаны в белорусских рублях.
              Бронь бесплатная, оплата — в павильоне наличными или картой.
            </p>
          </div>
        </div>
      </div>

      {filtersOpen && <button type="button" className="filter-overlay" aria-label="Закрыть фильтры" onClick={() => setFiltersOpen(false)} />}
    </div>
  )
}
