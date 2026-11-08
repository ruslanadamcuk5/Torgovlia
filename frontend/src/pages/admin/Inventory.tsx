import { useEffect, useMemo, useState } from 'react'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Loader, Modal, Spinner } from '../../components/ui'
import { Icon } from '../../components/icons'
import { formatQty, unitShort } from '../../lib/format'

interface InventoryItem {
  id: number
  title: string
  slug: string
  unit: 'kg' | 'piece'
  category_title: string | null
  stock: number | null
  price: number
  is_available: boolean
  is_out: boolean
  is_low: boolean
}

interface Movement {
  id: number
  product_id: number | null
  product_title: string
  kind: string
  kind_label: string
  quantity: number
  stock_before: number
  stock_after: number
  reason: string
  actor: string
  created_at: string
}

interface InventoryData {
  items: InventoryItem[]
  total: number
  summary: { tracked: number; low: number; out: number; threshold: number }
}

type MoveKind = 'in' | 'out' | 'adjust'

const KIND_TITLE: Record<MoveKind, string> = {
  in: 'Приход товара',
  out: 'Списание',
  adjust: 'Инвентаризация',
}

const KIND_HINT: Record<MoveKind, string> = {
  in: 'Укажите, сколько пришло. Остаток увеличится на это количество.',
  out: 'Спишите испорченный или использованный товар. Остаток уменьшится.',
  adjust: 'Введите фактическое количество на складе. Остаток станет равен этому числу.',
}

export default function Inventory() {
  const { toast } = useToast()
  const [query, setQuery] = useState('')
  const [lowOnly, setLowOnly] = useState(false)
  const [move, setMove] = useState<{ product: InventoryItem; kind: MoveKind } | null>(null)
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  const params = useMemo(() => {
    const search = new URLSearchParams()
    if (query.trim()) search.set('q', query.trim())
    if (lowOnly) search.set('low_only', 'true')
    return search.toString()
  }, [query, lowOnly])

  const { data, loading, reload } = useApi<InventoryData>(`/admin/inventory?${params}`)
  const { data: movements, reload: reloadMovements } = useApi<{ items: Movement[]; total: number }>(
    '/admin/inventory/movements?limit=40',
  )

  useEffect(() => {
    if (!move) return
    setAmount(move.kind === 'adjust' && move.product.stock !== null ? String(move.product.stock) : '')
    setReason('')
  }, [move])

  const openMove = (product: InventoryItem, kind: MoveKind) => setMove({ product, kind })

  const submit = async () => {
    if (!move) return
    const value = Number(amount.replace(',', '.'))
    if (!Number.isFinite(value) || value < 0) {
      toast('Укажите количество', 'error')
      return
    }
    setBusy(true)
    try {
      await api(`/admin/inventory/${move.product.id}/movement`, {
        method: 'POST',
        body: { kind: move.kind, quantity: value, reason },
      })
      toast(`${KIND_TITLE[move.kind]}: сохранено`)
      setMove(null)
      reload()
      reloadMovements()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить остаток', 'error')
    } finally {
      setBusy(false)
    }
  }

  if (loading || !data) return <Loader label="Загружаем склад…" />

  const summary = data.summary

  return (
    <div className="admin-page inventory-page">
      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Склад и остатки</h2>
            <p className="muted">
              Учитывайте приход, списание и фактический остаток. Брони уменьшают остаток автоматически,
              отмена возвращает товар.
            </p>
          </div>
          <label className="checkbox checkbox--inline">
            <input type="checkbox" checked={lowOnly} onChange={(event) => setLowOnly(event.target.checked)} />
            <span>Только заканчивающиеся</span>
          </label>
        </div>

        <div className="inventory-summary">
          <div><span>На учёте</span><strong>{summary.tracked}</strong></div>
          <div><span>Мало осталось</span><strong>{summary.low}</strong></div>
          <div><span>Нет в наличии</span><strong>{summary.out}</strong></div>
          <div><span>Порог предупреждения</span><strong>{summary.threshold} {summary.threshold === 1 ? 'ед.' : 'ед.'}</strong></div>
        </div>

        <label className="search-field inventory-search">
          <Icon name="search" size={16} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Название или категория" type="search" />
        </label>

        <div className="inventory-list">
          {data.items.map((product) => (
            <article className={`inventory-row ${product.is_out ? 'is-out' : product.is_low ? 'is-low' : ''}`} key={product.id}>
              <div className="inventory-row__main">
                <strong>{product.title}</strong>
                <small>{product.category_title ?? 'Без категории'} · цена за {unitShort(product.unit)}</small>
              </div>
              <div className="inventory-row__stock">
                {product.stock === null ? (
                  <span className="inventory-stock inventory-stock--none">Не учитывается</span>
                ) : (
                  <>
                    <b>{formatQty(product.stock)} {unitShort(product.unit)}</b>
                    <span className={`inventory-stock ${product.is_out ? 'inventory-stock--out' : product.is_low ? 'inventory-stock--low' : 'inventory-stock--ok'}`}>
                      {product.is_out ? 'Нет' : product.is_low ? 'Мало' : 'В наличии'}
                    </span>
                  </>
                )}
              </div>
              <div className="inventory-row__actions">
                <button type="button" className="btn btn--sm btn--outline" onClick={() => openMove(product, 'in')}>
                  <Icon name="plus" size={14} /> Приход
                </button>
                <button type="button" className="btn btn--sm btn--ghost" onClick={() => openMove(product, 'out')} disabled={product.stock === null || product.stock <= 0}>
                  <Icon name="minus" size={14} /> Списать
                </button>
                <button type="button" className="btn btn--sm btn--ghost" onClick={() => openMove(product, 'adjust')}>
                  <Icon name="edit" size={14} /> Пересчёт
                </button>
              </div>
            </article>
          ))}
          {data.items.length === 0 && <p className="muted">Ничего не найдено.</p>}
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h3>Последние операции</h3>
            <p className="muted">Приход, списание, брони и отмены — кто и когда изменил остаток.</p>
          </div>
        </div>
        <div className="inventory-history">
          {(movements?.items ?? []).map((row) => (
            <div className="inventory-move" key={row.id}>
              <span className={`inventory-move__sign ${row.quantity < 0 ? 'is-minus' : 'is-plus'}`}>
                {row.quantity > 0 ? '+' : ''}{formatQty(row.quantity)}
              </span>
              <div className="inventory-move__main">
                <strong>{row.product_title}</strong>
                <small>{row.kind_label} · {row.reason || 'без комментария'} · {row.actor}</small>
              </div>
              <div className="inventory-move__after">
                <b>{formatQty(row.stock_after)}</b>
                <small>{new Date(row.created_at).toLocaleString('ru-BY', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</small>
              </div>
            </div>
          ))}
          {(movements?.items ?? []).length === 0 && <p className="muted">Операций пока нет.</p>}
        </div>
      </section>

      {move && (
        <Modal
          title={`${KIND_TITLE[move.kind]} — ${move.product.title}`}
          subtitle={KIND_HINT[move.kind]}
          onClose={() => setMove(null)}
          size="sm"
          footer={
            <>
              <button type="button" className="btn btn--ghost" onClick={() => setMove(null)}>Отмена</button>
              <button type="button" className="btn btn--primary" onClick={submit} disabled={busy}>
                {busy ? <Spinner /> : null} Сохранить
              </button>
            </>
          }
        >
          <label className="field">
            <span className="field__label">
              Количество, {unitShort(move.product.unit)}
            </span>
            <input
              className="input"
              inputMode="decimal"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              autoFocus
            />
            {move.product.stock !== null && move.kind !== 'adjust' && (
              <span className="field__hint">Сейчас на складе: {formatQty(move.product.stock)} {unitShort(move.product.unit)}</span>
            )}
          </label>
          <label className="field">
            <span className="field__label">Комментарий</span>
            <input
              className="input"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder={move.kind === 'in' ? 'Поставщик, накладная' : move.kind === 'out' ? 'Причина списания' : 'Комментарий'}
            />
          </label>
        </Modal>
      )}
    </div>
  )
}
