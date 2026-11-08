import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, downloadFile } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Loader, Spinner } from '../../components/ui'
import { Icon } from '../../components/icons'
import { formatMoney, unitShort } from '../../lib/format'
import type { Category } from '../../lib/types'

type PreviewStatus = 'matched' | 'new' | 'invalid'
type RowAction = 'update' | 'create' | 'skip'

interface PreviewRow {
  line: number
  title: string
  price: number | null
  stock: number | null
  barcode: string
  unit: 'kg' | 'piece' | null
  category: string
  status: PreviewStatus
  message: string
  product_id: number | null
  product_title: string
  score: number
}

interface Preview {
  source: string
  filename: string
  delimiter: string
  headers: string[]
  total: number
  matched: number
  new: number
  invalid: number
  warnings: string[]
  rows: PreviewRow[]
}

interface ImportBatch {
  id: number
  filename: string
  source: string
  total: number
  updated: number
  created: number
  skipped: number
  errors: number
  actor: string
  messages: string[]
  created_at: string
}

const SOURCE_LABEL: Record<string, string> = {
  csv: 'CSV',
  xlsx: 'Excel',
  eml: 'Письмо',
  text: 'Текст',
}

const STATUS_LABEL: Record<PreviewStatus, string> = {
  matched: 'Совпадение',
  new: 'Новый',
  invalid: 'Пропуск',
}

export default function PriceImport() {
  const { toast } = useToast()
  const { data: features, loading: featuresLoading } = useApi<{ services: Record<string, boolean> }>('/admin/services/features')
  const enabled = Boolean(features?.services.price_import)
  const { data: categories } = useApi<{ items: Category[] }>(enabled ? '/admin/categories' : null)
  const { data: history, reload: reloadHistory } = useApi<{ items: ImportBatch[]; total: number }>(
    enabled ? '/admin/imports?limit=10' : null,
  )

  const [file, setFile] = useState<File | null>(null)
  const [text, setText] = useState('')
  const [preview, setPreview] = useState<Preview | null>(null)
  const [actions, setActions] = useState<Record<number, RowAction>>({})
  const [updatePrices, setUpdatePrices] = useState(true)
  const [updateStock, setUpdateStock] = useState(false)
  const [createMissing, setCreateMissing] = useState(false)
  const [categoryId, setCategoryId] = useState('')
  const [busy, setBusy] = useState(false)
  const [applying, setApplying] = useState(false)
  const [result, setResult] = useState<ImportBatch | null>(null)

  const chosenCount = useMemo(
    () => Object.values(actions).filter((action) => action !== 'skip').length,
    [actions],
  )

  useEffect(() => {
    setActions({})
    setResult(null)
  }, [preview])

  const parse = async () => {
    if (!file && !text.trim()) {
      toast('Загрузите файл или вставьте текст прайса', 'error')
      return
    }
    setBusy(true)
    try {
      const form = new FormData()
      if (file) form.append('file', file)
      if (text.trim()) form.append('text', text)
      const data = await api<Preview>('/admin/imports/preview', { method: 'POST', body: form })
      setPreview(data)
      const initial: Record<number, RowAction> = {}
      for (const row of data.rows) {
        initial[row.line] = row.status === 'matched' ? 'update' : 'skip'
      }
      setActions(initial)
      toast(`Распознано строк: ${data.total}`, data.invalid ? 'info' : undefined)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось разобрать прайс', 'error')
    } finally {
      setBusy(false)
    }
  }

  const toggleRow = (row: PreviewRow) => {
    setActions((current) => {
      const next = { ...current }
      if (next[row.line] && next[row.line] !== 'skip') next[row.line] = 'skip'
      else next[row.line] = row.status === 'new' ? 'create' : 'update'
      return next
    })
  }

  const apply = async () => {
    if (!preview) return
    const rows = preview.rows
      .map((row) => ({
        line: row.line,
        title: row.title,
        price: row.price,
        stock: row.stock,
        barcode: row.barcode,
        unit: row.unit,
        category: row.category,
        product_id: row.product_id,
        action: actions[row.line] ?? 'skip',
      }))
      .filter((row) => row.action !== 'skip')
    if (!rows.length) {
      toast('Выберите хотя бы одну строку', 'error')
      return
    }
    setApplying(true)
    try {
      const batch = await api<ImportBatch>('/admin/imports/apply', {
        method: 'POST',
        body: {
          filename: preview.filename,
          source: preview.source,
          rows,
          update_prices: updatePrices,
          update_stock: updateStock,
          create_missing: createMissing || rows.some((row) => row.action === 'create'),
          category_id: categoryId ? Number(categoryId) : null,
        },
      })
      setResult(batch)
      reloadHistory()
      toast(`Импорт: обновлено ${batch.updated}, создано ${batch.created}`, batch.errors ? 'info' : undefined)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось применить импорт', 'error')
    } finally {
      setApplying(false)
    }
  }

  if (featuresLoading) return <Loader />

  if (!enabled) {
    return (
      <div className="admin-page">
        <section className="panel panel--accent">
          <div className="panel__head"><h2>Импорт прайсов</h2></div>
          <p>
            Импорт прайсов доступен на тарифе <strong>«Про»</strong>. Сервис распознаёт
            CSV, Excel и письма, находит товары и обновляет цены и остатки.
          </p>
          <Link to="/admin/services" className="btn btn--primary">Перейти к сервисам <Icon name="arrow-right" size={17} /></Link>
        </section>
      </div>
    )
  }

  return (
    <div className="admin-page import-page">
      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Импорт прайсов</h2>
            <p className="muted">
              Загрузите CSV, Excel (.xlsx) или сохранённое письмо (.eml), либо вставьте
              таблицу из письма. Колонки распознаются по шапке: название, цена, остаток, штрихкод.
            </p>
          </div>
          <button
            type="button"
            className="btn btn--sm btn--ghost"
            onClick={() => void downloadFile('/admin/imports/template.csv', 'price-template.csv').catch(() => toast('Не удалось скачать шаблон', 'error'))}
          >
            <Icon name="download" size={15} /> Шаблон CSV
          </button>
        </div>

        <div className="import-source">
          <label className="field">
            <span className="field__label">Файл прайса</span>
            <input
              className="input import-file"
              type="file"
              accept=".csv,.tsv,.txt,.xlsx,.xlsm,.eml"
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null)
                setText('')
                setPreview(null)
              }}
            />
            <span className="field__hint">CSV, TSV, Excel .xlsx или письмо .eml. До 8 МБ, до 2000 строк.</span>
          </label>
          <div className="import-or">или</div>
          <label className="field">
            <span className="field__label">Текст письма или таблицы</span>
            <textarea
              className="textarea"
              rows={7}
              value={text}
              onChange={(event) => {
                setText(event.target.value)
                setFile(null)
                setPreview(null)
              }}
              placeholder={"Название;Цена;Остаток\nХуди оверсайз;79,00;18\nКуртка-бомбер;120,00;5"}
            />
          </label>
        </div>

        <div className="import-parse">
          <button type="button" className="btn btn--primary" onClick={parse} disabled={busy}>
            {busy ? <Spinner /> : <Icon name="upload" size={17} />} Проверить прайс
          </button>
          <span className="muted">Изменения не применяются до нажатия «Импортировать».</span>
        </div>
      </section>

      {preview && (
        <section className="panel">
          <div className="panel__head">
            <div>
              <h3>Проверка импорта</h3>
              <p className="muted">
                {preview.filename || 'Вставленный текст'} · {SOURCE_LABEL[preview.source] ?? preview.source} ·{' '}
                строк {preview.total}, совпало {preview.matched}, новых {preview.new}
                {preview.invalid ? `, пропущено ${preview.invalid}` : ''}
              </p>
            </div>
            <span className="muted">{chosenCount} к импорту</span>
          </div>

          {preview.warnings.length > 0 && (
            <div className="import-warnings">
              {preview.warnings.slice(0, 6).map((warning) => (
                <span key={warning}>{warning}</span>
              ))}
            </div>
          )}

          <div className="import-options">
            <label className="checkbox">
              <input type="checkbox" checked={updatePrices} onChange={(event) => setUpdatePrices(event.target.checked)} />
              <span>Обновлять цены</span>
            </label>
            <label className="checkbox">
              <input type="checkbox" checked={updateStock} onChange={(event) => setUpdateStock(event.target.checked)} />
              <span>Обновлять остатки</span>
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={createMissing}
                onChange={(event) => {
                  const value = event.target.checked
                  setCreateMissing(value)
                  setActions((current) => {
                    const next = { ...current }
                    for (const row of preview.rows) {
                      if (row.status === 'new') next[row.line] = value ? 'create' : 'skip'
                    }
                    return next
                  })
                }}
              />
              <span>Создавать новые товары</span>
            </label>
            <label className="field import-category">
              <span className="field__label">Категория для новых</span>
              <select className="input input--select" value={categoryId} onChange={(event) => setCategoryId(event.target.value)}>
                <option value="">Из файла или без категории</option>
                {categories?.items.map((category) => (
                  <option key={category.id} value={category.id}>{category.title}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="import-table-wrap">
            <table className="import-table">
              <thead>
                <tr>
                  <th />
                  <th>Стр.</th>
                  <th>Товар из прайса</th>
                  <th>Баркод</th>
                  <th>Цена</th>
                  <th>Остаток</th>
                  <th>Совпадение</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row) => {
                  const action = actions[row.line] ?? 'skip'
                  return (
                    <tr key={row.line} className={action === 'skip' ? 'is-skipped' : ''}>
                      <td>
                        <input
                          type="checkbox"
                          checked={action !== 'skip'}
                          onChange={() => toggleRow(row)}
                          aria-label={`Импортировать строку ${row.line}`}
                        />
                      </td>
                      <td className="import-table__num">{row.line}</td>
                      <td>
                        <strong>{row.title || 'Без названия'}</strong>
                        <small>{row.product_title ? `→ ${row.product_title}` : row.message}</small>
                      </td>
                      <td className="import-table__code">{row.barcode || '—'}</td>
                      <td className="import-table__num">{row.price != null ? formatMoney(row.price) : '—'}</td>
                      <td className="import-table__num">
                        {row.stock != null ? `${row.stock} ${row.unit ? unitShort(row.unit) : ''}` : '—'}
                      </td>
                      <td>
                        <span className={`import-status import-status--${row.status}`}>{STATUS_LABEL[row.status]}</span>
                        {row.status === 'matched' && row.score > 0 && row.score < 1 && (
                          <small className="import-score">{Math.round(row.score * 100)}%</small>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="import-apply">
            <button type="button" className="btn btn--primary" onClick={apply} disabled={applying || !chosenCount}>
              {applying ? <Spinner /> : <Icon name="check" size={17} />} Импортировать · {chosenCount}
            </button>
            <span className="muted">
              Цены {updatePrices ? 'обновляются' : 'не меняются'}, остатки {updateStock ? 'обновляются' : 'не меняются'}.
            </span>
          </div>
        </section>
      )}

      {result && (
        <section className="panel panel--accent">
          <div className="panel__head">
            <div>
              <h3>Импорт завершён</h3>
              <p className="muted">{result.filename || 'Прайс'} · {new Date(result.created_at).toLocaleString('ru-BY')}</p>
            </div>
          </div>
          <div className="import-result">
            <div><span>Обновлено</span><strong>{result.updated}</strong></div>
            <div><span>Создано</span><strong>{result.created}</strong></div>
            <div><span>Пропущено</span><strong>{result.skipped}</strong></div>
            <div><span>Ошибок</span><strong>{result.errors}</strong></div>
          </div>
          {result.messages.length > 0 && (
            <ul className="import-messages">
              {result.messages.slice(0, 12).map((message) => <li key={message}>{message}</li>)}
            </ul>
          )}
        </section>
      )}

      <section className="panel">
        <div className="panel__head">
          <h3>История импорта</h3>
          <span className="muted">{history?.total ?? 0} загрузок</span>
        </div>
        <div className="import-history">
          {(history?.items ?? []).map((batch) => (
            <div className="import-history__row" key={batch.id}>
              <div className="import-history__main">
                <strong>{batch.filename || 'Вставленный текст'}</strong>
                <small>
                  {SOURCE_LABEL[batch.source] ?? batch.source} · {new Date(batch.created_at).toLocaleString('ru-BY')} · {batch.actor}
                </small>
              </div>
              <div className="import-history__stats">
                <span>обновлено {batch.updated}</span>
                <span>создано {batch.created}</span>
                {batch.skipped > 0 && <span>пропущено {batch.skipped}</span>}
                {batch.errors > 0 && <span className="is-error">ошибок {batch.errors}</span>}
              </div>
            </div>
          ))}
          {(history?.items ?? []).length === 0 && (
            <p className="muted">Импортов ещё не было. Загрузите первый прайс — история появится здесь.</p>
          )}
        </div>
      </section>
    </div>
  )
}
