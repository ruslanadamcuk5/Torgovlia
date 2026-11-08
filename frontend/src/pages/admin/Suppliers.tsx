import { useMemo, useState } from 'react'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Loader, Modal, Spinner } from '../../components/ui'
import { Icon } from '../../components/icons'
import { formatMoney, formatQty, unitShort } from '../../lib/format'

interface Supplier {
  id: number
  name: string
  contact_person: string
  phone: string
  email: string
  address: string
  note: string
  is_active: boolean
  purchases_count: number
}

interface PurchaseRow {
  id: number
  product_id: number | null
  title: string
  unit: 'kg' | 'piece'
  quantity: number
  cost: number
  line_total: number
}

interface Purchase {
  id: number
  number: string
  supplier_id: number | null
  supplier_name: string
  status: string
  status_label: string
  expected_date: string | null
  received_at: string | null
  total_amount: number
  note: string
  created_at: string
  items: PurchaseRow[]
}

interface ProductOption {
  id: number
  title: string
  unit: 'kg' | 'piece'
  price: number
}

const EMPTY_SUPPLIER = {
  name: '',
  contact_person: '',
  phone: '',
  email: '',
  address: '',
  note: '',
  is_active: true,
}

type SupplierForm = typeof EMPTY_SUPPLIER

const TABS = [
  { id: 'suppliers', label: 'Поставщики' },
  { id: 'purchases', label: 'Закупки' },
]

const STATUS_TONE: Record<string, string> = {
  draft: 'draft',
  ordered: 'ordered',
  received: 'received',
  cancelled: 'cancelled',
}

export default function Suppliers() {
  const { toast } = useToast()
  const [tab, setTab] = useState<'suppliers' | 'purchases'>('suppliers')
  const [supplierQuery, setSupplierQuery] = useState('')
  const [purchaseStatus, setPurchaseStatus] = useState('all')
  const [supplierModal, setSupplierModal] = useState<Supplier | 'new' | null>(null)
  const [purchaseModal, setPurchaseModal] = useState(false)
  const [supplierForm, setSupplierForm] = useState<SupplierForm>({ ...EMPTY_SUPPLIER })
  const [busy, setBusy] = useState(false)
  const [acting, setActing] = useState<number | null>(null)

  const suppliers = useApi<{ items: Supplier[]; total: number }>(
    `/admin/suppliers${supplierQuery.trim() ? `?q=${encodeURIComponent(supplierQuery.trim())}` : ''}`,
  )
  const purchases = useApi<{ items: Purchase[]; total: number }>(
    `/admin/purchases?status=${purchaseStatus}`,
  )
  const products = useApi<{ items: ProductOption[]; total: number }>('/admin/products?limit=1000')

  const productOptions = useMemo(() => products.data?.items ?? [], [products.data])

  const openSupplier = (supplier: Supplier | 'new') => {
    setSupplierModal(supplier)
    if (supplier === 'new') {
      setSupplierForm({ ...EMPTY_SUPPLIER })
    } else {
      setSupplierForm({
        name: supplier.name,
        contact_person: supplier.contact_person,
        phone: supplier.phone,
        email: supplier.email,
        address: supplier.address,
        note: supplier.note,
        is_active: supplier.is_active,
      })
    }
  }

  const saveSupplier = async () => {
    if (!supplierForm.name.trim()) {
      toast('Укажите название поставщика', 'error')
      return
    }
    setBusy(true)
    try {
      if (supplierModal === 'new') {
        await api('/admin/suppliers', { method: 'POST', body: supplierForm })
        toast('Поставщик добавлен')
      } else if (supplierModal) {
        await api(`/admin/suppliers/${supplierModal.id}`, { method: 'PATCH', body: supplierForm })
        toast('Поставщик обновлён')
      }
      setSupplierModal(null)
      suppliers.reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить', 'error')
    } finally {
      setBusy(false)
    }
  }

  const removeSupplier = async (supplier: Supplier) => {
    if (!window.confirm(`Удалить поставщика «${supplier.name}»?`)) return
    setBusy(true)
    try {
      await api(`/admin/suppliers/${supplier.id}`, { method: 'DELETE' })
      toast('Поставщик удалён')
      suppliers.reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось удалить', 'error')
    } finally {
      setBusy(false)
    }
  }

  const changePurchase = async (purchase: Purchase, status: string) => {
    const labels: Record<string, string> = { received: 'Принять товар?', cancelled: 'Отменить закупку?' }
    if (!window.confirm(labels[status] ?? 'Изменить закупку?')) return
    setActing(purchase.id)
    try {
      await api(`/admin/purchases/${purchase.id}`, { method: 'PATCH', body: { status } })
      toast(status === 'received' ? 'Товар принят на склад' : 'Закупка обновлена')
      purchases.reload()
      suppliers.reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить закупку', 'error')
    } finally {
      setActing(null)
    }
  }

  const removePurchase = async (purchase: Purchase) => {
    if (!window.confirm(`Удалить закупку ${purchase.number}?`)) return
    setActing(purchase.id)
    try {
      await api(`/admin/purchases/${purchase.id}`, { method: 'DELETE' })
      toast('Закупка удалена')
      purchases.reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось удалить закупку', 'error')
    } finally {
      setActing(null)
    }
  }

  return (
    <div className="admin-page suppliers-page">
      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Поставщики и закупки</h2>
            <p className="muted">
              Карточки поставщиков, заявки на закупку и приёмка товара на склад. При приёмке остаток
              увеличивается автоматически и попадает в историю склада.
            </p>
          </div>
          <div className="supplier-tools">
            <button type="button" className="btn btn--outline" onClick={() => openSupplier('new')}>
              <Icon name="plus" size={16} /> Поставщик
            </button>
            <button type="button" className="btn btn--primary" onClick={() => setPurchaseModal(true)}>
              <Icon name="plus" size={16} /> Закупка
            </button>
          </div>
        </div>

        <div className="segmented supplier-tabs">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={tab === item.id ? 'is-active' : ''}
              onClick={() => setTab(item.id as 'suppliers' | 'purchases')}
            >
              {item.label}
            </button>
          ))}
        </div>
      </section>

      {tab === 'suppliers' && (
        <section className="panel">
          <div className="panel__head">
            <div>
              <h3>Поставщики</h3>
              <p className="muted">{suppliers.data?.total ?? 0} в справочнике</p>
            </div>
            <label className="search-field supplier-search">
              <Icon name="search" size={16} />
              <input
                value={supplierQuery}
                onChange={(event) => setSupplierQuery(event.target.value)}
                placeholder="Название, контакт или телефон"
                type="search"
              />
            </label>
          </div>

          {suppliers.loading ? (
            <Loader label="Загружаем поставщиков…" />
          ) : (
            <div className="supplier-list">
              {(suppliers.data?.items ?? []).map((supplier) => (
                <article className={`supplier-row ${supplier.is_active ? '' : 'is-inactive'}`} key={supplier.id}>
                  <div className="supplier-row__avatar">{supplier.name.slice(0, 1).toUpperCase()}</div>
                  <div className="supplier-row__main">
                    <div className="supplier-row__title">
                      <strong>{supplier.name}</strong>
                      {!supplier.is_active && <span className="supplier-badge">Неактивен</span>}
                    </div>
                    <small>
                      {supplier.contact_person || 'Контакт не указан'}
                      {supplier.phone ? ` · ${supplier.phone}` : ''}
                      {supplier.email ? ` · ${supplier.email}` : ''}
                    </small>
                    {supplier.address && <small className="supplier-row__address">{supplier.address}</small>}
                  </div>
                  <div className="supplier-row__stats">
                    <strong>{supplier.purchases_count}</strong>
                    <small>закупок</small>
                  </div>
                  <div className="supplier-row__actions">
                    <button type="button" className="btn btn--sm btn--ghost" onClick={() => openSupplier(supplier)}>
                      <Icon name="edit" size={14} /> Изменить
                    </button>
                    <button
                      type="button"
                      className="btn btn--sm btn--ghost"
                      onClick={() => removeSupplier(supplier)}
                      disabled={busy}
                    >
                      <Icon name="trash" size={14} />
                    </button>
                  </div>
                </article>
              ))}
              {(suppliers.data?.items ?? []).length === 0 && (
                <p className="muted">Поставщиков пока нет. Добавьте первого — и создавайте закупки.</p>
              )}
            </div>
          )}
        </section>
      )}

      {tab === 'purchases' && (
        <section className="panel">
          <div className="panel__head">
            <div>
              <h3>Закупки</h3>
              <p className="muted">{purchases.data?.total ?? 0} заявок</p>
            </div>
            <div className="purchase-filters">
              {[
                ['all', 'Все'],
                ['draft', 'Черновики'],
                ['ordered', 'Заказано'],
                ['received', 'Принято'],
                ['cancelled', 'Отменено'],
              ].map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  className={`btn btn--sm ${purchaseStatus === value ? 'btn--primary' : 'btn--ghost'}`}
                  onClick={() => setPurchaseStatus(value)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {purchases.loading ? (
            <Loader label="Загружаем закупки…" />
          ) : (
            <div className="purchase-list">
              {(purchases.data?.items ?? []).map((purchase) => (
                <article className="purchase-card" key={purchase.id}>
                  <div className="purchase-card__head">
                    <div>
                      <strong>{purchase.number}</strong>
                      <small>
                        {purchase.supplier_name || 'Без поставщика'}
                        {purchase.expected_date
                          ? ` · ожидается ${new Date(purchase.expected_date).toLocaleDateString('ru-BY')}`
                          : ''}
                      </small>
                    </div>
                    <div className="purchase-card__right">
                      <span className={`purchase-status purchase-status--${STATUS_TONE[purchase.status] ?? 'draft'}`}>
                        {purchase.status_label}
                      </span>
                      <strong>{formatMoney(purchase.total_amount)}</strong>
                    </div>
                  </div>

                  <div className="purchase-items">
                    {purchase.items.map((item) => (
                      <div className="purchase-item" key={item.id}>
                        <span>{item.title}</span>
                        <span>
                          {formatQty(item.quantity)} {unitShort(item.unit)} × {formatMoney(item.cost)}
                        </span>
                        <b>{formatMoney(item.line_total)}</b>
                      </div>
                    ))}
                  </div>

                  {purchase.note && <p className="purchase-note">{purchase.note}</p>}

                  <div className="purchase-card__actions">
                    {(purchase.status === 'draft' || purchase.status === 'ordered') && (
                      <>
                        <button
                          type="button"
                          className="btn btn--sm btn--primary"
                          onClick={() => changePurchase(purchase, 'received')}
                          disabled={acting === purchase.id}
                        >
                          {acting === purchase.id ? <Spinner /> : <Icon name="check" size={14} />} Принять на склад
                        </button>
                        <button
                          type="button"
                          className="btn btn--sm btn--ghost"
                          onClick={() => changePurchase(purchase, 'cancelled')}
                          disabled={acting === purchase.id}
                        >
                          Отменить
                        </button>
                      </>
                    )}
                    {(purchase.status === 'draft' || purchase.status === 'cancelled') && (
                      <button
                        type="button"
                        className="btn btn--sm btn--ghost"
                        onClick={() => removePurchase(purchase)}
                        disabled={acting === purchase.id}
                      >
                        <Icon name="trash" size={14} /> Удалить
                      </button>
                    )}
                  </div>
                </article>
              ))}
              {(purchases.data?.items ?? []).length === 0 && (
                <p className="muted">Закупок пока нет. Создайте заявку — при приёмке товар попадёт на склад.</p>
              )}
            </div>
          )}
        </section>
      )}

      {supplierModal && (
        <Modal
          title={supplierModal === 'new' ? 'Новый поставщик' : 'Поставщик'}
          onClose={() => setSupplierModal(null)}
          size="sm"
          footer={
            <>
              <button type="button" className="btn btn--ghost" onClick={() => setSupplierModal(null)}>
                Отмена
              </button>
              <button type="button" className="btn btn--primary" onClick={saveSupplier} disabled={busy}>
                {busy ? <Spinner /> : null} Сохранить
              </button>
            </>
          }
        >
          <label className="field">
            <span className="field__label">Название</span>
            <input
              className="input"
              value={supplierForm.name}
              onChange={(event) => setSupplierForm({ ...supplierForm, name: event.target.value })}
              placeholder="ООО «Поставка»"
              autoFocus
            />
          </label>
          <div className="form-grid">
            <label className="field">
              <span className="field__label">Контактное лицо</span>
              <input
                className="input"
                value={supplierForm.contact_person}
                onChange={(event) => setSupplierForm({ ...supplierForm, contact_person: event.target.value })}
              />
            </label>
            <label className="field">
              <span className="field__label">Телефон</span>
              <input
                className="input"
                value={supplierForm.phone}
                onChange={(event) => setSupplierForm({ ...supplierForm, phone: event.target.value })}
                placeholder="+375 29 000-00-00"
              />
            </label>
          </div>
          <label className="field">
            <span className="field__label">Email</span>
            <input
              className="input"
              value={supplierForm.email}
              onChange={(event) => setSupplierForm({ ...supplierForm, email: event.target.value })}
              placeholder="supply@example.by"
            />
          </label>
          <label className="field">
            <span className="field__label">Адрес</span>
            <input
              className="input"
              value={supplierForm.address}
              onChange={(event) => setSupplierForm({ ...supplierForm, address: event.target.value })}
            />
          </label>
          <label className="field">
            <span className="field__label">Условия и заметки</span>
            <textarea
              className="textarea"
              rows={3}
              value={supplierForm.note}
              onChange={(event) => setSupplierForm({ ...supplierForm, note: event.target.value })}
              placeholder="Отсрочка, минимальная партия, доставка"
            />
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={supplierForm.is_active}
              onChange={(event) => setSupplierForm({ ...supplierForm, is_active: event.target.checked })}
            />
            <span>Активный поставщик</span>
          </label>
        </Modal>
      )}

      {purchaseModal && (
        <PurchaseModal
          suppliers={suppliers.data?.items ?? []}
          products={productOptions}
          onClose={() => setPurchaseModal(false)}
          onSaved={() => {
            setPurchaseModal(false)
            purchases.reload()
            suppliers.reload()
            setTab('purchases')
          }}
        />
      )}
    </div>
  )
}

function PurchaseModal({
  suppliers,
  products,
  onClose,
  onSaved,
}: {
  suppliers: Supplier[]
  products: ProductOption[]
  onClose: () => void
  onSaved: () => void
}) {
  const { toast } = useToast()
  const [supplierId, setSupplierId] = useState('')
  const [expectedDate, setExpectedDate] = useState('')
  const [note, setNote] = useState('')
  const [rows, setRows] = useState([{ productId: '', quantity: '1', cost: '' }])
  const [busy, setBusy] = useState(false)

  const setRow = (index: number, patch: Partial<(typeof rows)[number]>) => {
    setRows((current) => current.map((row, position) => (position === index ? { ...row, ...patch } : row)))
  }

  const total = rows.reduce((sum, row) => {
    const value = Number(row.quantity.replace(',', '.')) * Number(row.cost.replace(',', '.'))
    return sum + (Number.isFinite(value) ? value : 0)
  }, 0)

  const save = async () => {
    const items = rows
      .filter((row) => row.productId)
      .map((row) => ({
        product_id: Number(row.productId),
        quantity: Number(row.quantity.replace(',', '.')),
        cost: Number((row.cost || '0').replace(',', '.')),
      }))
    if (!items.length) {
      toast('Добавьте хотя бы один товар', 'error')
      return
    }
    if (items.some((item) => !Number.isFinite(item.quantity) || item.quantity <= 0)) {
      toast('Укажите количество больше нуля', 'error')
      return
    }
    setBusy(true)
    try {
      await api('/admin/purchases', {
        method: 'POST',
        body: {
          supplier_id: supplierId ? Number(supplierId) : null,
          expected_date: expectedDate || null,
          note,
          items,
        },
      })
      toast('Закупка создана')
      onSaved()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось создать закупку', 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      title="Новая закупка"
      subtitle="Укажите поставщика и товары. При приёмке остаток пополнится на складе."
      onClose={onClose}
      size="lg"
      footer={
        <>
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Отмена
          </button>
          <button type="button" className="btn btn--primary" onClick={save} disabled={busy}>
            {busy ? <Spinner /> : null} Создать закупку
          </button>
        </>
      }
    >
      <div className="form-grid">
        <label className="field">
          <span className="field__label">Поставщик</span>
          <select className="input" value={supplierId} onChange={(event) => setSupplierId(event.target.value)}>
            <option value="">Без поставщика</option>
            {suppliers
              .filter((supplier) => supplier.is_active)
              .map((supplier) => (
                <option key={supplier.id} value={supplier.id}>
                  {supplier.name}
                </option>
              ))}
          </select>
        </label>
        <label className="field">
          <span className="field__label">Ожидаемая дата</span>
          <input
            className="input"
            type="date"
            value={expectedDate}
            onChange={(event) => setExpectedDate(event.target.value)}
          />
        </label>
      </div>

      <div className="purchase-editor">
        {rows.map((row, index) => (
          <div className="purchase-editor__row" key={index}>
            <label className="field">
              <span className="field__label">Товар</span>
              <select
                className="input"
                value={row.productId}
                onChange={(event) => setRow(index, { productId: event.target.value })}
              >
                <option value="">Выберите товар</option>
                {products.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field__label">Количество</span>
              <input
                className="input"
                inputMode="decimal"
                value={row.quantity}
                onChange={(event) => setRow(index, { quantity: event.target.value })}
              />
            </label>
            <label className="field">
              <span className="field__label">Цена закупки</span>
              <input
                className="input"
                inputMode="decimal"
                value={row.cost}
                onChange={(event) => setRow(index, { cost: event.target.value })}
                placeholder="0,00"
              />
            </label>
            <button
              type="button"
              className="btn btn--ghost purchase-editor__remove"
              onClick={() => setRows((current) => current.filter((_, position) => position !== index))}
              disabled={rows.length === 1}
              aria-label="Убрать строку"
            >
              <Icon name="trash" size={15} />
            </button>
          </div>
        ))}
        <div className="purchase-editor__footer">
          <button
            type="button"
            className="btn btn--sm btn--outline"
            onClick={() => setRows((current) => [...current, { productId: '', quantity: '1', cost: '' }])}
          >
            <Icon name="plus" size={14} /> Добавить товар
          </button>
          <strong>Итого: {formatMoney(total)}</strong>
        </div>
      </div>

      <label className="field">
        <span className="field__label">Комментарий</span>
        <textarea
          className="textarea"
          rows={2}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Накладная, условия доставки"
        />
      </label>
    </Modal>
  )
}
