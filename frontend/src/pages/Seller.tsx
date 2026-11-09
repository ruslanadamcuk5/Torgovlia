import { useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, assetUrl, uploadImage } from '../lib/api'
import { useApi } from '../lib/useApi'
import { useAuth } from '../store/AuthContext'
import { useSite } from '../store/SettingsContext'
import { useToast } from '../store/ToastContext'
import { EmptyState, Loader, Modal, Spinner, StatusBadge } from '../components/ui'
import { Icon } from '../components/icons'
import type { Category, Order, Product, StaffTask } from '../lib/types'
import { formatMoney, formatQty, humanDate, statusLabel, unitShort } from '../lib/format'

interface Summary {
  user: { full_name: string; role: string }
  products_total: number
  out_of_stock: number
  new_orders: number
  ready_orders: number
  pickups_today: Order[]
  tasks_enabled: boolean
  tasks_open: number
  today: string
}

type Tab = 'orders' | 'products' | 'add' | 'tasks'
type ProductForm = {
  title: string
  unit: 'kg' | 'piece'
  price: string
  stock: string
  weight_note: string
  short_description: string
  category_id: string
  is_available: boolean
  image_url: string
}

const EMPTY_PRODUCT: ProductForm = {
  title: '',
  unit: 'kg',
  price: '',
  stock: '',
  weight_note: '',
  short_description: '',
  category_id: '',
  is_available: true,
  image_url: '',
}

function taskDueLabel(task: StaffTask): string {
  if (task.overdue) return 'Просрочено'
  if (task.due_today) return 'Сегодня'
  if (!task.due_date) return ''
  return new Date(`${task.due_date}T00:00:00`).toLocaleDateString('ru-BY', { day: 'numeric', month: 'short' })
}

const NEXT: Record<string, { status: string; label: string; icon: 'check' | 'box' | 'close'; danger?: boolean }[]> = {
  new: [
    { status: 'confirmed', label: 'Подтвердить бронь', icon: 'check' },
    { status: 'rejected', label: 'Отклонить', icon: 'close', danger: true },
  ],
  confirmed: [
    { status: 'ready', label: 'Собрано — готово к выдаче', icon: 'box' },
    { status: 'cancelled', label: 'Отменить', icon: 'close', danger: true },
  ],
  ready: [
    { status: 'completed', label: 'Выдать покупателю', icon: 'check' },
    { status: 'cancelled', label: 'Отменить', icon: 'close', danger: true },
  ],
}

export default function Seller() {
  const { user, logout, isAdmin } = useAuth()
  const { site } = useSite()
  const { toast } = useToast()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('orders')
  const [query, setQuery] = useState('')
  const [editor, setEditor] = useState<Product | 'new' | null>(null)
  const [form, setForm] = useState<ProductForm>(EMPTY_PRODUCT)
  const [busy, setBusy] = useState(false)
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const summary = useApi<Summary>('/seller/summary')
  const orders = useApi<{ items: Order[]; total: number }>('/seller/orders?status=active&limit=200')
  const products = useApi<{ items: Product[]; total: number }>('/seller/products?limit=300')
  const categories = useApi<Category[]>('/seller/categories')
  const tasks = useApi<{ items: StaffTask[]; summary: { open: number; today: number; overdue: number } }>(
    summary.data?.tasks_enabled ? '/seller/tasks' : null,
  )

  const visibleProducts = useMemo(() => {
    const rows = products.data?.items ?? []
    const term = query.trim().toLowerCase()
    if (!term) return rows
    return rows.filter((product) => `${product.title} ${product.category_title ?? ''}`.toLowerCase().includes(term))
  }, [products.data, query])

  if (!site || !user) return null
  const s = site.settings

  const openEditor = (product: Product | 'new') => {
    setEditor(product)
    setForm(product === 'new' ? EMPTY_PRODUCT : {
      title: product.title,
      unit: product.unit,
      price: String(product.price),
      stock: product.stock != null ? String(product.stock) : '',
      weight_note: product.weight_note ?? '',
      short_description: product.short_description ?? '',
      category_id: product.category_id ? String(product.category_id) : '',
      is_available: product.is_available,
      image_url: product.image_url ?? '',
    })
    if (product === 'new') setTab('add')
  }

  const closeEditor = () => {
    setEditor(null)
    if (tab === 'add') setTab('products')
  }

  const saveProduct = async () => {
    if (form.title.trim().length < 2) return toast('Укажите название товара', 'error')
    if (!form.price || Number(form.price) <= 0) return toast('Укажите цену', 'error')
    setBusy(true)
    try {
      const body = {
        title: form.title.trim(),
        unit: form.unit,
        price: Number(form.price),
        stock: form.stock === '' ? null : Number(form.stock),
        weight_note: form.weight_note.trim(),
        short_description: form.short_description.trim(),
        category_id: form.category_id ? Number(form.category_id) : null,
        is_available: form.is_available,
        image_url: form.image_url || null,
      }
      if (editor === 'new') {
        await api<Product>('/seller/products', { method: 'POST', body })
        toast('Товар добавлен в каталог')
      } else if (editor) {
        await api<Product>(`/seller/products/${editor.id}`, { method: 'PATCH', body })
        toast('Товар обновлён')
      }
      closeEditor()
      summary.reload()
      products.reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить товар', 'error')
    } finally {
      setBusy(false)
    }
  }

  const toggleAvailability = async (product: Product) => {
    try {
      await api<Product>(`/seller/products/${product.id}/availability?is_available=${!product.is_available}`, { method: 'POST' })
      toast(product.is_available ? `«${product.title}» — нет в наличии` : `«${product.title}» — снова в продаже`)
      products.reload()
      summary.reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось обновить наличие', 'error')
    }
  }

  const changeStatus = async (order: Order, status: string) => {
    setBusy(true)
    try {
      await api<Order>(`/seller/orders/${order.id}/status`, { method: 'PATCH', body: { status } })
      toast(`${order.number}: ${statusLabel(status).toLowerCase()}`)
      orders.reload()
      summary.reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить статус', 'error')
    } finally {
      setBusy(false)
    }
  }

  const changeTaskStatus = async (task: StaffTask, status: 'todo' | 'in_progress' | 'done') => {
    setBusy(true)
    try {
      await api<StaffTask>(`/seller/tasks/${task.id}`, { method: 'PATCH', body: { status } })
      toast(status === 'done' ? 'Задача закрыта' : status === 'in_progress' ? 'Задача взята в работу' : 'Задача возвращена')
      tasks.reload()
      summary.reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось обновить задачу', 'error')
    } finally {
      setBusy(false)
    }
  }

  const uploadPhoto = async (file?: File) => {
    if (!file) return
    setUploading(true)
    try {
      const result = await uploadImage(file, '/seller/uploads')
      setForm((current) => ({ ...current, image_url: result.url }))
      toast('Фото загружено')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось загрузить фото', 'error')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const orderRows = orders.data?.items ?? []

  return (
    <div className="seller-app">
      <header className="seller-header">
        <div className="seller-header__brand">
          <img src={assetUrl(s.logo_url)} alt="" width={42} height={42} />
          <div>
            <strong>{s.brand_name}</strong>
            <span>{user.full_name} · {user.role === 'admin' ? 'администратор' : 'продавец'}</span>
          </div>
        </div>
        <div className="seller-header__actions">
          {isAdmin && <Link to="/admin" className="icon-btn" title="Админ-панель"><Icon name="dashboard" size={20} /></Link>}
          <Link to="/" className="icon-btn" title="Открыть сайт"><Icon name="external" size={20} /></Link>
          <button type="button" className="icon-btn" title="Выйти" onClick={() => { logout(); navigate('/') }}><Icon name="logout" size={20} /></button>
        </div>
      </header>

      <main className="seller-main">
        <section className="seller-greeting">
          <div>
            <span className="eyebrow">Рабочий режим · {new Date().toLocaleDateString('ru-BY', { weekday: 'long', day: 'numeric', month: 'long' })}</span>
            <h1>Здравствуйте, {user.full_name.split(' ')[0]}!</h1>
            <p>{s.city}, {s.market_name}, {s.pavilion}</p>
          </div>
          <div className="seller-greeting__status">
            <span className={`dot ${site.today.is_closed ? 'dot--muted' : ''}`} />
            {site.today.is_closed ? 'Сегодня закрыто' : `Открыто до ${site.today.close}`}
          </div>
        </section>

        <div className="seller-stats">
          <button type="button" className="seller-stat seller-stat--warn" onClick={() => setTab('orders')}>
            <span><Icon name="bell" size={22} /></span>
            <strong>{summary.data?.new_orders ?? 0}</strong>
            <small>новых броней</small>
          </button>
          <button type="button" className="seller-stat seller-stat--success" onClick={() => setTab('orders')}>
            <span><Icon name="box" size={22} /></span>
            <strong>{summary.data?.ready_orders ?? 0}</strong>
            <small>готовы к выдаче</small>
          </button>
          <button type="button" className="seller-stat" onClick={() => setTab('products')}>
            <span><Icon name="fish" size={22} /></span>
            <strong>{summary.data?.products_total ?? 0}</strong>
            <small>товаров в каталоге</small>
          </button>
          <button type="button" className="seller-stat" onClick={() => setTab('products')}>
            <span><Icon name="alert" size={22} /></span>
            <strong>{summary.data?.out_of_stock ?? 0}</strong>
            <small>нет в наличии</small>
          </button>
        </div>

        {tab === 'orders' && (
          <section className="seller-section">
            <div className="seller-section__head">
              <div><h2>Брони в работе</h2><p>Сначала заказы на ближайшее время</p></div>
              <button type="button" className="icon-btn" onClick={() => { orders.reload(); summary.reload() }} title="Обновить"><Icon name="refresh" size={20} /></button>
            </div>

            {orders.loading ? <Loader /> : orderRows.length > 0 ? (
              <div className="seller-orders">
                {orderRows.map((order) => {
                  const actions = NEXT[order.status] ?? []
                  const soon = order.pickup_date === summary.data?.today
                  return (
                    <article className={`seller-order ${soon ? 'is-today' : ''}`} key={order.id}>
                      <div className="seller-order__head">
                        <div>
                          <span className="seller-order__number">{order.number}</span>
                          <strong>{order.customer_name}</strong>
                        </div>
                        <StatusBadge status={order.status} />
                      </div>

                      <div className="seller-order__pickup">
                        <span className="seller-order__time">{order.pickup_time}</span>
                        <div>
                          <strong>{soon ? 'Сегодня' : humanDate(order.pickup_date)}</strong>
                          <span>{order.phone_formatted}</span>
                        </div>
                        <a href={`tel:${order.phone}`} className="btn btn--sm btn--outline"><Icon name="phone" size={16} /> Позвонить</a>
                      </div>

                      <ul className="seller-order__items">
                        {order.items.map((item) => (
                          <li key={item.id}>
                            <span>{item.title}</span>
                            <strong>{formatQty(item.quantity)} {unitShort(item.unit)}</strong>
                            <b>{formatMoney(item.line_total)}</b>
                          </li>
                        ))}
                      </ul>

                      {order.comment && (
                        <div className="seller-order__comment"><Icon name="edit" size={16} /><span>{order.comment}</span></div>
                      )}

                      <div className="seller-order__foot">
                        <span>Итого <strong>{formatMoney(order.total_amount)}</strong></span>
                        <div className="seller-order__actions">
                          {actions.map((action) => (
                            <button
                              key={action.status}
                              type="button"
                              className={`btn btn--lg ${action.danger ? 'btn--danger-ghost' : 'btn--primary'}`}
                              disabled={busy}
                              onClick={() => void changeStatus(order, action.status)}
                            >
                              <Icon name={action.icon} size={19} /> {action.label}
                            </button>
                          ))}
                          {actions.length === 0 && <span className="muted">Заказ завершён</span>}
                        </div>
                      </div>
                    </article>
                  )
                })}
              </div>
            ) : (
              <EmptyState icon="check" title="Активных броней нет" text="Новые заказы появятся здесь автоматически. Обновляйте список в течение дня." />
            )}
          </section>
        )}

        {tab === 'tasks' && (
          <section className="seller-section">
            <div className="seller-section__head">
              <div><h2>Мои задачи</h2><p>Поручения от администратора магазина</p></div>
              <button type="button" className="icon-btn" onClick={() => { tasks.reload(); summary.reload() }} title="Обновить"><Icon name="refresh" size={20} /></button>
            </div>

            {tasks.loading ? <Loader /> : (tasks.data?.items.length ?? 0) > 0 ? (
              <div className="seller-tasks">
                {tasks.data?.items.map((task) => (
                  <article className={`seller-task ${task.overdue ? 'is-overdue' : ''}`} key={task.id}>
                    <header>
                      <div>
                        <strong>{task.title}</strong>
                        <span className={`task-priority task-priority--${task.priority}`}>
                          {task.priority === 'high' ? 'Важно' : task.priority === 'low' ? 'Не срочно' : 'Обычно'}
                        </span>
                      </div>
                      {taskDueLabel(task) && (
                        <span className={`task-due task-due--${task.overdue ? 'danger' : task.due_today ? 'warn' : 'muted'}`}>
                          {taskDueLabel(task)}
                        </span>
                      )}
                    </header>
                    {task.description && <p>{task.description}</p>}
                    {task.order && (
                      <Link to="/seller" className="seller-task__order">
                        <Icon name="list" size={14} /> Заказ {task.order.number} · {task.order.customer_name}
                      </Link>
                    )}
                    <div className="seller-task__actions">
                      {task.status === 'todo' && (
                        <button type="button" className="btn btn--sm btn--outline" disabled={busy} onClick={() => void changeTaskStatus(task, 'in_progress')}>
                          В работу
                        </button>
                      )}
                      {task.status !== 'done' && (
                        <button type="button" className="btn btn--sm btn--primary" disabled={busy} onClick={() => void changeTaskStatus(task, 'done')}>
                          <Icon name="check" size={15} /> Готово
                        </button>
                      )}
                      {task.status === 'done' && (
                        <button type="button" className="btn btn--sm btn--outline" disabled={busy} onClick={() => void changeTaskStatus(task, 'todo')}>
                          Вернуть в работу
                        </button>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState icon="check" title="Задач нет" text="Когда администратор назначит поручение, оно появится здесь." />
            )}
          </section>
        )}

        {(tab === 'products' || tab === 'add') && (
          <section className="seller-section">
            <div className="seller-section__head">
              <div><h2>Товары</h2><p>Наличие и цены обновляются сразу на сайте</p></div>
              <button type="button" className="btn btn--primary" onClick={() => openEditor('new')}><Icon name="plus" size={18} /> Добавить</button>
            </div>

            <label className="search-field search-field--large">
              <Icon name="search" size={19} />
              <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Найти товар" />
            </label>

            {products.loading ? <Loader /> : visibleProducts.length > 0 ? (
              <div className="seller-products">
                {visibleProducts.map((product) => (
                  <article className={`seller-product ${!product.is_available ? 'is-out' : ''} ${!product.is_active ? 'is-hidden' : ''}`} key={product.id}>
                    <div className="seller-product__img">
                      {product.image_url ? <img src={assetUrl(product.image_url)} alt="" /> : <Icon name="fish" size={26} />}
                    </div>
                    <div className="seller-product__info">
                      <strong>{product.title}</strong>
                      <span>{formatMoney(product.price)} / {unitShort(product.unit)} {product.stock != null ? `· ${formatQty(product.stock)} ${unitShort(product.unit)}` : ''}</span>
                      {!product.is_active && <span className="badge badge--muted">скрыт с сайта</span>}
                    </div>
                    <div className="seller-product__actions">
                      <button
                        type="button"
                        className={`seller-toggle ${product.is_available ? 'is-on' : ''}`}
                        onClick={() => void toggleAvailability(product)}
                      >
                        <span>{product.is_available ? 'В наличии' : 'Нет в наличии'}</span>
                        <span className="switch"><span /></span>
                      </button>
                      <button type="button" className="btn btn--outline" onClick={() => openEditor(product)}>
                        <Icon name="edit" size={17} /> Изменить
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState icon="fish" title="Товары не найдены" text="Измените поиск или добавьте новую позицию." action={<button type="button" className="btn btn--primary" onClick={() => openEditor('new')}>Добавить товар</button>} />
            )}
          </section>
        )}
      </main>

      <nav className="seller-nav">
        <button type="button" className={tab === 'orders' ? 'is-active' : ''} onClick={() => setTab('orders')}>
          <Icon name="list" size={23} /><span>Брони</span>
          {(summary.data?.new_orders ?? 0) > 0 && <b>{summary.data?.new_orders}</b>}
        </button>
        <button type="button" className={`seller-nav__add ${tab === 'add' ? 'is-active' : ''}`} onClick={() => openEditor('new')}>
          <span><Icon name="plus" size={27} /></span><span>Добавить</span>
        </button>
        <button type="button" className={tab === 'products' ? 'is-active' : ''} onClick={() => setTab('products')}>
          <Icon name="fish" size={23} /><span>Товары</span>
        </button>
        {summary.data?.tasks_enabled && (
          <button type="button" className={tab === 'tasks' ? 'is-active' : ''} onClick={() => setTab('tasks')}>
            <Icon name="check" size={23} /><span>Задачи</span>
            {(summary.data?.tasks_open ?? 0) > 0 && <b>{summary.data?.tasks_open}</b>}
          </button>
        )}
      </nav>

      {editor && (
        <Modal
          title={editor === 'new' ? 'Добавить товар' : 'Изменить товар'}
          subtitle={editor === 'new' ? 'Сфотографируйте товар и укажите цену — он сразу появится на сайте' : editor.title}
          size="lg"
          onClose={closeEditor}
          footer={(
            <>
              <button type="button" className="btn btn--ghost btn--lg" onClick={closeEditor}>Отмена</button>
              <button type="button" className="btn btn--primary btn--lg" onClick={saveProduct} disabled={busy || uploading}>
                {busy ? <Spinner size={18} /> : <Icon name="check" size={18} />} Сохранить
              </button>
            </>
          )}
        >
          <div className="seller-form">
            <div className="seller-photo">
              <div className={`seller-photo__preview ${form.image_url ? 'has-image' : ''}`}>
                {form.image_url ? <img src={assetUrl(form.image_url)} alt="" /> : <><Icon name="camera" size={34} /><span>Добавьте фото</span></>}
                {uploading && <div className="seller-photo__loading"><Spinner size={26} /></div>}
              </div>
              <div className="seller-photo__actions">
                <button type="button" className="btn btn--primary btn--lg" onClick={() => fileRef.current?.click()} disabled={uploading}>
                  <Icon name="camera" size={19} /> Сделать фото
                </button>
                <button type="button" className="btn btn--outline" onClick={() => fileRef.current?.click()} disabled={uploading}>
                  <Icon name="upload" size={18} /> Из галереи
                </button>
                {form.image_url && <button type="button" className="link-btn" onClick={() => setForm({ ...form, image_url: '' })}>Удалить фото</button>}
                <input ref={fileRef} type="file" accept="image/*" capture="environment" hidden onChange={(event) => void uploadPhoto(event.target.files?.[0])} />
              </div>
            </div>

            <label className="field">
              <span className="field__label">Название *</span>
              <input className="input input--lg" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="Например, Сельдь слабосолёная" />
            </label>

            <div className="form-grid">
              <label className="field">
                <span className="field__label">Цена, BYN *</span>
                <input className="input input--lg" type="number" step="0.01" value={form.price} onChange={(event) => setForm({ ...form, price: event.target.value })} placeholder="0,00" inputMode="decimal" />
              </label>
              <label className="field">
                <span className="field__label">За что цена</span>
                <select className="input input--lg input--select" value={form.unit} onChange={(event) => setForm({ ...form, unit: event.target.value as 'kg' | 'piece' })}>
                  <option value="kg">За килограмм</option>
                  <option value="piece">За штуку</option>
                </select>
              </label>
            </div>

            <div className="form-grid">
              <label className="field">
                <span className="field__label">Категория</span>
                <select className="input input--select" value={form.category_id} onChange={(event) => setForm({ ...form, category_id: event.target.value })}>
                  <option value="">Без категории</option>
                  {(categories.data ?? []).map((category) => <option key={category.id} value={category.id}>{category.title}</option>)}
                </select>
              </label>
              <label className="field">
                <span className="field__label">Остаток</span>
                <input className="input" type="number" step="0.1" value={form.stock} onChange={(event) => setForm({ ...form, stock: event.target.value })} placeholder="не ограничен" />
              </label>
            </div>

            <label className="field">
              <span className="field__label">Короткое описание</span>
              <textarea className="textarea" rows={2} value={form.short_description} onChange={(event) => setForm({ ...form, short_description: event.target.value })} placeholder="Пара слов о товаре для карточки" />
            </label>

            <label className="field">
              <span className="field__label">Примечание к весу</span>
              <input className="input" value={form.weight_note} onChange={(event) => setForm({ ...form, weight_note: event.target.value })} placeholder="Например: тушка 300–500 г" />
            </label>

            <label className="seller-availability">
              <div>
                <strong>Есть в наличии</strong>
                <span>Покупатели смогут забронировать товар</span>
              </div>
              <input type="checkbox" checked={form.is_available} onChange={(event) => setForm({ ...form, is_available: event.target.checked })} />
              <span className="switch" />
            </label>
          </div>
        </Modal>
      )}
    </div>
  )
}
