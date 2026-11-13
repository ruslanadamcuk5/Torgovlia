import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
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
  { value: 'title', label: 'По названию' },
]

export default function ServicesPage() {
  const { site } = useSite()
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState(params.get('q') ?? '')
  const debouncedQuery = useDebounced(query, 350)
  const [sort, setSort] = useState('default')
  const [filtersOpen, setFiltersOpen] = useState(false)
  const category = params.get('category') ?? ''

  const { data: categories } = useApi<Category[]>('/categories', false)
  const path = useMemo(() => {
    const search = new URLSearchParams({ limit: '100', sort })
    if (category) search.set('category', category)
    if (debouncedQuery.trim()) search.set('q', debouncedQuery.trim())
    return `/services?${search.toString()}`
  }, [category, debouncedQuery, sort])

  const { data, loading } = useApi<{ items: Product[]; total: number }>(path, false)

  const setCategory = (slug: string) => {
    const next = new URLSearchParams(params)
    if (slug) next.set('category', slug)
    else next.delete('category')
    setParams(next, { replace: true })
    setFiltersOpen(false)
  }

  if (!site) return null
  const activeCategory = categories?.find((item) => item.slug === category)

  return (
    <div className="catalog-page">
      <div className="page-head page-head--services">
        <div className="container">
          <div className="breadcrumbs">
            <Link to="/">Главная</Link><Icon name="chevron-right" size={13} /><span>Услуги</span>
            {activeCategory && <><Icon name="chevron-right" size={13} /><span>{activeCategory.title}</span></>}
          </div>
          <div className="page-head__row">
            <div>
              <span className="eyebrow">Каталог услуг</span>
              <h1>{activeCategory?.title ?? 'Услуги и цены'}</h1>
              <p className="page-head__sub">
                {activeCategory?.description || 'Выберите услугу, специалиста и удобное время — запись без звонков.'}
              </p>
            </div>
            <div className="page-head__badge">
              <Icon name="calendar" size={20} />
              <span>Онлайн-запись 24/7</span>
            </div>
          </div>
        </div>
      </div>

      <div className="container catalog-layout">
        <aside className={`filters ${filtersOpen ? 'is-open' : ''}`}>
          <div className="filters__mobile-head">
            <strong>Направления</strong>
            <button type="button" className="icon-btn" onClick={() => setFiltersOpen(false)} aria-label="Закрыть">
              <Icon name="close" size={22} />
            </button>
          </div>

          <div className="filters__group">
            <span className="filters__title">Направление</span>
            <button
              type="button"
              className={`filters__cat ${category === '' ? 'is-active' : ''}`}
              onClick={() => setCategory('')}
            >
              <span>Все услуги</span>
              <em>{data?.total ?? 0}</em>
            </button>
            {categories?.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`filters__cat ${category === item.slug ? 'is-active' : ''}`}
                onClick={() => setCategory(item.slug)}
              >
                <span>{item.title}</span>
                <em>{item.products_count}</em>
              </button>
            ))}
          </div>

          <div className="filters__hint">
            <Icon name="clock" size={18} />
            <span>Время и длительность услуги видны до записи. Оплата — на месте.</span>
          </div>

          <button type="button" className="btn btn--primary btn--block" onClick={() => setFiltersOpen(false)}>
            Показать услуги
          </button>
        </aside>

        <div className="catalog-main">
          <div className="catalog-toolbar">
            <div className="catalog-search">
              <Icon name="search" size={18} />
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Найти услугу"
                aria-label="Поиск услуг"
              />
            </div>
            <div className="catalog-toolbar__right">
              <button type="button" className="btn btn--ghost btn--sm filters-toggle" onClick={() => setFiltersOpen(true)}>
                <Icon name="menu" size={17} /> Направления
              </button>
              <select className="input input--sm" value={sort} onChange={(event) => setSort(event.target.value)} aria-label="Сортировка">
                {SORTS.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="catalog-count">
            {loading ? 'Загружаем услуги…' : `Найдено: ${data?.total ?? 0}`}
          </div>

          {data?.items.length ? (
            <div className="product-grid product-grid--four">
              {data.items.map((service) => (
                <ProductCard key={service.id} product={service} />
              ))}
            </div>
          ) : !loading ? (
            <div className="empty-state">
              <span className="empty-state__icon"><Icon name="search" size={28} /></span>
              <h3>Услуги не найдены</h3>
              <p>Попробуйте изменить направление или запрос. Или позвоните — подберём время вручную.</p>
              <Link to="/booking" className="btn btn--primary">Записаться без выбора</Link>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
