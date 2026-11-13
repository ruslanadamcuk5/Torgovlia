import { useEffect, useMemo, useState } from 'react'
import { api, assetUrl } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { ImageUpload } from '../../components/ImageUpload'
import { Barcode } from '../../components/Barcode'
import { Loader, Modal, Spinner } from '../../components/ui'
import { Icon } from '../../components/icons'
import type { Category, Product } from '../../lib/types'
import { formatMoney, formatQty, unitShort } from '../../lib/format'

type Draft = {
  title: string
  subtitle: string
  slug: string
  category_id: string
  unit: 'kg' | 'piece'
  kind: 'goods' | 'service'
  duration_minutes: string
  buffer_minutes: string
  capacity: string
  price: string
  discount_percent: string
  stock: string
  weight_note: string
  barcode: string
  image_url: string
  badges: string
  short_description: string
  description: string
  origin: string
  season: string
  cooking_tips: string
  storage_tips: string
  sort_order: string
  is_available: boolean
  is_active: boolean
  is_daily_deal: boolean
  kcal: string
  protein: string
  fat: string
  omega3: string
}

const EMPTY: Draft = {
  title: '',
  subtitle: '',
  slug: '',
  category_id: '',
  unit: 'kg',
  kind: 'goods',
  duration_minutes: '60',
  buffer_minutes: '10',
  capacity: '1',
  price: '',
  discount_percent: '0',
  stock: '',
  weight_note: '',
  barcode: '',
  image_url: '',
  badges: '',
  short_description: '',
  description: '',
  origin: '',
  season: '',
  cooking_tips: '',
  storage_tips: '',
  sort_order: '100',
  is_available: true,
  is_active: true,
  is_daily_deal: false,
  kcal: '',
  protein: '',
  fat: '',
  omega3: '',
}

function toDraft(product: Product): Draft {
  const nutrition = product.nutrition ?? {}
  return {
    title: product.title,
    subtitle: product.subtitle ?? '',
    slug: product.slug,
    category_id: product.category_id ? String(product.category_id) : '',
    unit: product.unit,
    kind: product.kind === 'service' ? 'service' : 'goods',
    duration_minutes: String(product.duration_minutes || 60),
    buffer_minutes: String(product.buffer_minutes || 0),
    capacity: String(product.capacity || 1),
    price: String(product.price),
    discount_percent: String(product.discount_percent ?? 0),
    stock: product.stock != null ? String(product.stock) : '',
    weight_note: product.weight_note ?? '',
    barcode: product.barcode ?? '',
    image_url: product.image_url ?? '',
    badges: (product.badges ?? []).join(', '),
    short_description: product.short_description ?? '',
    description: product.description ?? '',
    origin: product.origin ?? '',
    season: product.season ?? '',
    cooking_tips: product.cooking_tips ?? '',
    storage_tips: product.storage_tips ?? '',
    sort_order: String(product.sort_order ?? 100),
    is_available: product.is_available,
    is_active: product.is_active,
    is_daily_deal: product.is_daily_deal,
    kcal: nutrition.kcal != null ? String(nutrition.kcal) : '',
    protein: nutrition.protein != null ? String(nutrition.protein) : '',
    fat: nutrition.fat != null ? String(nutrition.fat) : '',
    omega3: nutrition.omega3 != null ? String(nutrition.omega3) : '',
  }
}

export default function CatalogAdmin() {
  const { toast } = useToast()
  const [query, setQuery] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [view, setView] = useState<'all' | 'active' | 'hidden' | 'out'>('all')
  const [editing, setEditing] = useState<Product | 'new' | null>(null)
  const [draft, setDraft] = useState<Draft>(EMPTY)
  const [busy, setBusy] = useState(false)
  const [categoriesOpen, setCategoriesOpen] = useState(false)

  const categories = useApi<{ items: Category[] }>('/admin/categories')
  const params = new URLSearchParams({ limit: '500', include_inactive: 'true' })
  if (query.trim()) params.set('q', query.trim())
  if (categoryId) params.set('category_id', categoryId)
  const { data, loading, reload } = useApi<{ items: Product[]; total: number }>(`/admin/products?${params.toString()}`)

  const items = useMemo(() => {
    const rows = data?.items ?? []
    if (view === 'active') return rows.filter((product) => product.is_active)
    if (view === 'hidden') return rows.filter((product) => !product.is_active)
    if (view === 'out') return rows.filter((product) => product.is_active && !product.is_available)
    return rows
  }, [data, view])

  useEffect(() => {
    if (!editing) return
    setDraft(editing === 'new' ? { ...EMPTY, category_id: categoryId } : toDraft(editing))
  }, [editing, categoryId])

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((current) => ({ ...current, [key]: value }))

  const save = async () => {
    if (draft.title.trim().length < 2) return toast('Укажите название товара', 'error')
    if (!draft.price || Number(draft.price) < 0) return toast('Укажите корректную цену', 'error')
    setBusy(true)
    try {
      const nutrition: Record<string, number> = {}
      if (draft.kcal) nutrition.kcal = Number(draft.kcal)
      if (draft.protein) nutrition.protein = Number(draft.protein)
      if (draft.fat) nutrition.fat = Number(draft.fat)
      if (draft.omega3) nutrition.omega3 = Number(draft.omega3)

      const payload = {
        title: draft.title.trim(),
        subtitle: draft.subtitle.trim(),
        slug: draft.slug.trim() || undefined,
        category_id: draft.category_id ? Number(draft.category_id) : null,
        unit: draft.unit,
        kind: draft.kind,
        duration_minutes: draft.kind === 'service' ? Number(draft.duration_minutes) || 60 : 0,
        buffer_minutes: draft.kind === 'service' ? Number(draft.buffer_minutes) || 0 : 0,
        capacity: draft.kind === 'service' ? Number(draft.capacity) || 1 : 1,
        price: Number(draft.price),
        discount_percent: Number(draft.discount_percent) || 0,
        stock: draft.stock === '' ? null : Number(draft.stock),
        weight_note: draft.weight_note.trim(),
        barcode: draft.barcode.trim() || null,
        image_url: draft.image_url || null,
        badges: draft.badges.split(',').map((badge) => badge.trim()).filter(Boolean),
        short_description: draft.short_description.trim(),
        description: draft.description.trim(),
        origin: draft.origin.trim(),
        season: draft.season.trim(),
        cooking_tips: draft.cooking_tips.trim(),
        storage_tips: draft.storage_tips.trim(),
        nutrition,
        sort_order: Number(draft.sort_order) || 100,
        is_available: draft.is_available,
        is_active: draft.is_active,
        is_daily_deal: draft.is_daily_deal,
      }

      if (editing === 'new') {
        await api<Product>('/admin/products', { method: 'POST', body: payload })
        toast('Товар добавлен в каталог')
      } else if (editing) {
        await api<Product>(`/admin/products/${editing.id}`, { method: 'PATCH', body: payload })
        toast('Изменения сохранены')
      }
      setEditing(null)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить товар', 'error')
    } finally {
      setBusy(false)
    }
  }

  const quickToggle = async (product: Product, field: 'is_available' | 'is_active') => {
    try {
      await api<Product>(`/admin/products/${product.id}`, {
        method: 'PATCH',
        body: { [field]: !product[field] },
      })
      toast(field === 'is_available'
        ? (product.is_available ? 'Отмечено «нет в наличии»' : 'Товар снова в наличии')
        : (product.is_active ? 'Товар скрыт из каталога' : 'Товар опубликован'))
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось обновить товар', 'error')
    }
  }

  const generateBarcode = async () => {
    if (editing === 'new' || !editing) return
    setBusy(true)
    try {
      const updated = await api<Product>(`/admin/products/${editing.id}/barcode`, { method: 'POST' })
      setDraft((current) => ({ ...current, barcode: updated.barcode ?? '' }))
      toast('Штрихкод создан')
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось создать штрихкод', 'error')
    } finally {
      setBusy(false)
    }
  }

  const remove = async (product: Product) => {
    if (!window.confirm(`Снять «${product.title}» с продажи? Товар исчезнет из каталога, история заказов сохранится.`)) return
    try {
      await api(`/admin/products/${product.id}`, { method: 'DELETE' })
      toast('Товар снят с продажи')
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось удалить товар', 'error')
    }
  }

  return (
    <div className="admin-page">
      <div className="admin-toolbar">
        <div className="admin-toolbar__left">
          <label className="search-field">
            <Icon name="search" size={17} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Название или адрес товара" type="search" />
          </label>
          <select className="input input--sm input--select" value={categoryId} onChange={(event) => setCategoryId(event.target.value)}>
            <option value="">Все категории</option>
            {categories.data?.items.map((category) => (
              <option key={category.id} value={category.id}>{category.title}</option>
            ))}
          </select>
        </div>
        <div className="admin-toolbar__right">
          <span className="muted">{items.length} из {data?.total ?? 0}</span>
          <button type="button" className="btn btn--sm btn--outline" onClick={() => setCategoriesOpen(true)}>
            <Icon name="tag" size={16} /> Категории
          </button>
          <button type="button" className="btn btn--sm btn--primary" onClick={() => setEditing('new')}>
            <Icon name="plus" size={16} /> Добавить товар
          </button>
        </div>
      </div>

      <div className="admin-tabs">
        {([
          ['all', 'Все товары'],
          ['active', 'Опубликованы'],
          ['hidden', 'Скрыты'],
          ['out', 'Нет в наличии'],
        ] as const).map(([id, label]) => (
          <button key={id} type="button" className={view === id ? 'is-active' : ''} onClick={() => setView(id)}>{label}</button>
        ))}
      </div>

      {loading ? <Loader /> : items.length > 0 ? (
        <div className="table-wrap">
          <table className="data-table data-table--products">
            <thead>
              <tr>
                <th>Товар</th>
                <th>Цена</th>
                <th>Остаток</th>
                <th>Наличие</th>
                <th>Публикация</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((product) => (
                <tr key={product.id}>
                  <td>
                    <div className="table-product">
                      <span className="table-product__img">
                        {product.image_url ? <img src={assetUrl(product.image_url)} alt="" /> : <Icon name="image" size={20} />}
                      </span>
                      <div>
                        <strong>{product.title}</strong>
                        <span className="table-sub">{product.category_title ?? 'Без категории'} · {product.slug}</span>
                      </div>
                    </div>
                  </td>
                  <td>
                    <strong>{formatMoney(product.final_price)}</strong>
                    <span className="table-sub">
                      {product.kind === 'service'
                        ? `${product.duration_minutes} мин`
                        : `/ ${unitShort(product.unit)}`}
                    </span>
                    {product.kind === 'service' && <span className="badge badge--info">услуга</span>}
                    {product.discount_percent > 0 && <span className="badge badge--sale">−{product.discount_percent}%</span>}
                  </td>
                  <td>{product.stock != null ? `${formatQty(product.stock)} ${unitShort(product.unit)}` : <span className="muted">не задан</span>}</td>
                  <td>
                    <button
                      type="button"
                      className={`switch-button ${product.is_available ? 'is-on' : ''}`}
                      onClick={() => void quickToggle(product, 'is_available')}
                      title="Переключить наличие"
                    >
                      <span className="switch-button__dot" />
                      {product.is_available ? 'В наличии' : 'Нет'}
                    </button>
                  </td>
                  <td>
                    <button
                      type="button"
                      className={`switch-button ${product.is_active ? 'is-on' : ''}`}
                      onClick={() => void quickToggle(product, 'is_active')}
                      title="Опубликовать или скрыть"
                    >
                      <span className="switch-button__dot" />
                      {product.is_active ? 'Опубликован' : 'Скрыт'}
                    </button>
                  </td>
                  <td>
                    <div className="row row--nowrap">
                      <a href={`/fish/${product.slug}`} target="_blank" rel="noreferrer" className="icon-btn" title="Открыть на сайте">
                        <Icon name="eye" size={17} />
                      </a>
                      <button type="button" className="icon-btn" title="Редактировать" onClick={() => setEditing(product)}>
                        <Icon name="edit" size={17} />
                      </button>
                      <button type="button" className="icon-btn icon-btn--danger" title="Снять с продажи" onClick={() => void remove(product)}>
                        <Icon name="trash" size={17} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state">
          <span className="empty-state__icon"><Icon name="box" size={28} /></span>
          <h3>Товаров нет</h3>
          <p>Измените фильтры или добавьте первый товар в каталог.</p>
          <button type="button" className="btn btn--primary" onClick={() => setEditing('new')}>Добавить товар</button>
        </div>
      )}

      {editing && (
        <Modal
          title={editing === 'new' ? 'Новый товар' : `Редактирование: ${editing.title}`}
          subtitle="Карточка товара, цена, наличие и описание"
          size="lg"
          onClose={() => setEditing(null)}
          footer={(
            <>
              <button type="button" className="btn btn--ghost" onClick={() => setEditing(null)}>Отмена</button>
              <button type="button" className="btn btn--primary" onClick={save} disabled={busy}>
                {busy ? <Spinner size={17} /> : <Icon name="check" size={17} />} Сохранить
              </button>
            </>
          )}
        >
          <div className="product-editor">
            <div className="product-editor__main">
              <div className="form-grid">
                <label className="field">
                  <span className="field__label">Название *</span>
                  <input className="input" value={draft.title} onChange={(event) => set('title', event.target.value)} placeholder="Например, Форель радужная" />
                </label>
                <label className="field">
                  <span className="field__label">Подзаголовок</span>
                  <input className="input" value={draft.subtitle} onChange={(event) => set('subtitle', event.target.value)} placeholder="Короткая строка под названием" />
                </label>
              </div>

              <div className="form-grid form-grid--three">
                <label className="field">
                  <span className="field__label">Категория</span>
                  <select className="input input--select" value={draft.category_id} onChange={(event) => set('category_id', event.target.value)}>
                    <option value="">Без категории</option>
                    {categories.data?.items.map((category) => <option key={category.id} value={category.id}>{category.title}</option>)}
                  </select>
                </label>
                <label className="field">
                  <span className="field__label">Единица</span>
                  <select className="input input--select" value={draft.unit} onChange={(event) => set('unit', event.target.value as 'kg' | 'piece')}>
                    <option value="kg">За килограмм</option>
                    <option value="piece">За штуку</option>
                  </select>
                </label>
                <label className="field">
                  <span className="field__label">Порядок вывода</span>
                  <input className="input" type="number" value={draft.sort_order} onChange={(event) => set('sort_order', event.target.value)} />
                </label>
              </div>

              <div className="form-grid form-grid--three">
                <label className="field">
                  <span className="field__label">Тип позиции</span>
                  <select className="input input--select" value={draft.kind} onChange={(event) => set('kind', event.target.value as 'goods' | 'service')}>
                    <option value="goods">Товар</option>
                    <option value="service">Услуга</option>
                  </select>
                  <span className="field__hint">
                    {draft.kind === 'service'
                      ? 'Услуга попадает в каталог услуг и онлайн-запись.'
                      : 'Обычная товарная позиция с корзиной и остатками.'}
                  </span>
                </label>
                {draft.kind === 'service' ? (
                  <>
                    <label className="field">
                      <span className="field__label">Длительность, минут</span>
                      <input className="input" type="number" min="5" max="720" step="5" value={draft.duration_minutes} onChange={(event) => set('duration_minutes', event.target.value)} />
                    </label>
                    <label className="field">
                      <span className="field__label">Буфер после визита, минут</span>
                      <input className="input" type="number" min="0" max="180" step="5" value={draft.buffer_minutes} onChange={(event) => set('buffer_minutes', event.target.value)} />
                    </label>
                  </>
                ) : (
                  <label className="field">
                    <span className="field__label">Единица продажи</span>
                    <select className="input input--select" value={draft.unit} onChange={(event) => set('unit', event.target.value as 'kg' | 'piece')}>
                      <option value="kg">За килограмм</option>
                      <option value="piece">За штуку</option>
                    </select>
                  </label>
                )}
              </div>

              {draft.kind === 'service' && (
                <div className="form-grid form-grid--three">
                  <label className="field">
                    <span className="field__label">Мест без специалиста</span>
                    <input className="input" type="number" min="1" max="100" value={draft.capacity} onChange={(event) => set('capacity', event.target.value)} />
                    <span className="field__hint">Сколько клиентов можно принять на одно время, если мастера не выбраны.</span>
                  </label>
                </div>
              )}

              <div className="form-grid form-grid--three">
                <label className="field">
                  <span className="field__label">Цена, BYN *</span>
                  <input className="input" type="number" step="0.01" min="0" value={draft.price} onChange={(event) => set('price', event.target.value)} />
                </label>
                <label className="field">
                  <span className="field__label">Скидка, %</span>
                  <input className="input" type="number" min="0" max="95" value={draft.discount_percent} onChange={(event) => set('discount_percent', event.target.value)} />
                </label>
                <label className="field">
                  <span className="field__label">Остаток</span>
                  <input className="input" type="number" step="0.1" min="0" value={draft.stock} onChange={(event) => set('stock', event.target.value)} placeholder="Не ограничен" />
                </label>
              </div>

              <label className="field">
                <span className="field__label">Примечание к весу</span>
                <input className="input" value={draft.weight_note} onChange={(event) => set('weight_note', event.target.value)} placeholder="Например: тушка 300–500 г, возможен раздела" />
              </label>

              <div className="barcode-field">
                <label className="field">
                  <span className="field__label">Штрихкод EAN-13</span>
                  <input
                    className="input"
                    value={draft.barcode}
                    onChange={(event) => set('barcode', event.target.value.replace(/[^\d]/g, '').slice(0, 13))}
                    inputMode="numeric"
                    placeholder="Создастся автоматически"
                  />
                  <span className="field__hint">Используется для сканирования и печати этикеток 58 × 40 мм.</span>
                </label>
                <div className="barcode-field__action">
                  {draft.barcode && <Barcode code={draft.barcode} height={34} />}
                  {editing !== 'new' && !draft.barcode && (
                    <button type="button" className="btn btn--sm btn--ghost" onClick={generateBarcode} disabled={busy}>
                      <Icon name="tag" size={14} /> Создать код
                    </button>
                  )}
                </div>
              </div>

              <label className="field">
                <span className="field__label">Краткое описание для карточки</span>
                <textarea className="textarea" rows={2} value={draft.short_description} onChange={(event) => set('short_description', event.target.value)} />
                <span className="field__hint">Показывается в каталоге и в превью статьи.</span>
              </label>

              <label className="field">
                <span className="field__label">Описание товара (Markdown)</span>
                <textarea className="textarea" rows={10} value={draft.description} onChange={(event) => set('description', event.target.value)} placeholder={"## Происхождение\n\nТекст статьи…\n\n## Как приготовить\n\n• Совет 1\n• Совет 2"} />
                <span className="field__hint">Поддерживаются заголовки ##, списки • и выделение **жирным**.</span>
              </label>

              <div className="form-grid">
                <label className="field">
                  <span className="field__label">Как приготовить</span>
                  <textarea className="textarea" rows={3} value={draft.cooking_tips} onChange={(event) => set('cooking_tips', event.target.value)} />
                </label>
                <label className="field">
                  <span className="field__label">Как хранить</span>
                  <textarea className="textarea" rows={3} value={draft.storage_tips} onChange={(event) => set('storage_tips', event.target.value)} />
                </label>
              </div>

              <div className="form-grid form-grid--four">
                <label className="field"><span className="field__label">Происхождение</span><input className="input" value={draft.origin} onChange={(event) => set('origin', event.target.value)} placeholder="Беларусь" /></label>
                <label className="field"><span className="field__label">Сезон</span><input className="input" value={draft.season} onChange={(event) => set('season', event.target.value)} placeholder="Круглый год" /></label>
                <label className="field"><span className="field__label">Белки, г</span><input className="input" type="number" step="0.1" value={draft.protein} onChange={(event) => set('protein', event.target.value)} /></label>
                <label className="field"><span className="field__label">Жиры, г</span><input className="input" type="number" step="0.1" value={draft.fat} onChange={(event) => set('fat', event.target.value)} /></label>
              </div>
              <div className="form-grid form-grid--three">
                <label className="field"><span className="field__label">Калорийность</span><input className="input" type="number" value={draft.kcal} onChange={(event) => set('kcal', event.target.value)} /></label>
                <label className="field"><span className="field__label">Омега-3, г</span><input className="input" type="number" step="0.1" value={draft.omega3} onChange={(event) => set('omega3', event.target.value)} /></label>
                <label className="field"><span className="field__label">Метки через запятую</span><input className="input" value={draft.badges} onChange={(event) => set('badges', event.target.value)} placeholder="Хит продаж, Новинка" /></label>
              </div>
            </div>

            <aside className="product-editor__side">
              <ImageUpload
                value={draft.image_url}
                onChange={(url) => set('image_url', url)}
                label="Фото товара"
                hint="JPEG, PNG или WebP до 8 МБ. Изображение автоматически сжимается в WebP."
              />
              <div className="panel panel--soft">
                <h3>Публикация</h3>
                <label className="switch-row">
                  <span>В наличии</span>
                  <input type="checkbox" checked={draft.is_available} onChange={(event) => set('is_available', event.target.checked)} />
                  <span className="switch" />
                </label>
                <label className="switch-row">
                  <span>Опубликован</span>
                  <input type="checkbox" checked={draft.is_active} onChange={(event) => set('is_active', event.target.checked)} />
                  <span className="switch" />
                </label>
                <label className="switch-row">
                  <span>Товар дня</span>
                  <input type="checkbox" checked={draft.is_daily_deal} onChange={(event) => set('is_daily_deal', event.target.checked)} />
                  <span className="switch" />
                </label>
                <p className="field__hint">Товар дня показывается на главной отдельным блоком. Одновременно можно выбрать один товар.</p>
              </div>
              <div className="panel panel--soft">
                <h3>Адрес страницы</h3>
                <label className="field">
                  <span className="field__label">Slug</span>
                  <input className="input" value={draft.slug} onChange={(event) => set('slug', event.target.value)} placeholder="создастся автоматически" />
                  <span className="field__hint">/fish/{draft.slug || 'avtomaticheski'}</span>
                </label>
                <p className="field__hint">Меняйте адрес только если на старый не ведут QR-коды. Иначе перепечатайте QR.</p>
              </div>
            </aside>
          </div>
        </Modal>
      )}

      {categoriesOpen && (
        <CategoryManager
          items={categories.data?.items ?? []}
          onClose={() => setCategoriesOpen(false)}
          onChanged={() => { categories.reload(); reload() }}
        />
      )}
    </div>
  )
}

function CategoryManager({ items, onClose, onChanged }: { items: Category[]; onClose: () => void; onChanged: () => void }) {
  const { toast } = useToast()
  const [editing, setEditing] = useState<Category | 'new' | null>(null)
  const [title, setTitle] = useState('')
  const [slug, setSlug] = useState('')
  const [description, setDescription] = useState('')
  const [imageUrl, setImageUrl] = useState('')
  const [sortOrder, setSortOrder] = useState('100')
  const [isActive, setIsActive] = useState(true)
  const [busy, setBusy] = useState(false)

  const start = (category: Category | 'new') => {
    setEditing(category)
    if (category === 'new') {
      setTitle(''); setSlug(''); setDescription(''); setImageUrl(''); setSortOrder('100'); setIsActive(true)
    } else {
      setTitle(category.title)
      setSlug(category.slug)
      setDescription(category.description)
      setImageUrl(category.image_url ?? '')
      setSortOrder(String(category.sort_order))
      setIsActive(category.is_active)
    }
  }

  const save = async () => {
    if (title.trim().length < 2) return toast('Укажите название категории', 'error')
    setBusy(true)
    try {
      const payload = { title: title.trim(), description, image_url: imageUrl || null, sort_order: Number(sortOrder) || 0, is_active: isActive }
      if (editing === 'new') {
        await api('/admin/categories', { method: 'POST', body: { ...payload, slug: slug.trim() || undefined } })
        toast('Категория создана')
      } else if (editing) {
        await api(`/admin/categories/${editing.id}`, { method: 'PATCH', body: payload })
        toast('Категория обновлена')
      }
      setEditing(null)
      onChanged()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить категорию', 'error')
    } finally {
      setBusy(false)
    }
  }

  const remove = async (category: Category) => {
    if (!window.confirm(`Удалить категорию «${category.title}»?`)) return
    try {
      await api(`/admin/categories/${category.id}`, { method: 'DELETE' })
      toast('Категория удалена')
      onChanged()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось удалить категорию', 'error')
    }
  }

  return (
    <Modal
      title="Категории каталога"
      subtitle={`${items.length} категорий · товары распределяются по разделам`}
      size="lg"
      onClose={onClose}
      footer={<button type="button" className="btn btn--ghost" onClick={onClose}>Закрыть</button>}
    >
      <div className="category-manager">
        <div className="category-manager__list">
          {items.map((category) => (
            <div className="category-row" key={category.id}>
              <div>
                <strong>{category.title}</strong>
                <span className="table-sub">{category.slug} · {category.products_count} товаров · порядок {category.sort_order}</span>
              </div>
              <span className={`badge ${category.is_active ? 'badge--fresh' : 'badge--muted'}`}>{category.is_active ? 'активна' : 'скрыта'}</span>
              <div className="row row--nowrap">
                <button type="button" className="icon-btn" onClick={() => start(category)}><Icon name="edit" size={17} /></button>
                <button type="button" className="icon-btn icon-btn--danger" onClick={() => void remove(category)}><Icon name="trash" size={17} /></button>
              </div>
            </div>
          ))}
          {items.length === 0 && <p className="muted">Категорий пока нет.</p>}
        </div>

        <div className="category-manager__form">
          {!editing ? (
            <button type="button" className="btn btn--primary btn--block" onClick={() => start('new')}>
              <Icon name="plus" size={17} /> Новая категория
            </button>
          ) : (
            <>
              <div className="panel__head">
                <h3>{editing === 'new' ? 'Новая категория' : 'Редактирование'}</h3>
                <button type="button" className="link-btn" onClick={() => setEditing(null)}>Отмена</button>
              </div>
              <label className="field"><span className="field__label">Название *</span><input className="input" value={title} onChange={(event) => setTitle(event.target.value)} /></label>
              {editing === 'new' && (
                <label className="field"><span className="field__label">Slug</span><input className="input" value={slug} onChange={(event) => setSlug(event.target.value)} placeholder="создастся автоматически" /></label>
              )}
              <label className="field"><span className="field__label">Описание</span><textarea className="textarea" rows={2} value={description} onChange={(event) => setDescription(event.target.value)} /></label>
              <label className="field"><span className="field__label">Порядок</span><input className="input" type="number" value={sortOrder} onChange={(event) => setSortOrder(event.target.value)} /></label>
              <ImageUpload value={imageUrl} onChange={setImageUrl} label="Изображение категории" />
              <label className="switch-row">
                <span>Активна</span>
                <input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} />
                <span className="switch" />
              </label>
              <button type="button" className="btn btn--primary btn--block" onClick={save} disabled={busy}>
                {busy ? <Spinner size={17} /> : 'Сохранить категорию'}
              </button>
            </>
          )}
        </div>
      </div>
    </Modal>
  )
}
