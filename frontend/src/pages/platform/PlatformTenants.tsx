import { useState } from 'react'
import { Link } from 'react-router-dom'
import { platformApi, usePlatformApi } from '../../lib/platformApi'
import { useToast } from '../../store/ToastContext'
import { Modal } from '../../components/ui'
import type { PlatformPlan, PlatformCatalog, Tenant } from '../../lib/types'

const STATUS_LABEL: Record<string, string> = {
  draft: 'Черновик',
  onboarding: 'Настройка',
  active: 'Активен',
  grace: 'Отсрочка',
  suspended: 'Приостановлен',
  archived: 'Архив',
}

const PRESETS = [
  { code: 'fish', label: 'Рыба и морепродукты' },
  { code: 'meat', label: 'Мясо и птица' },
  { code: 'flowers', label: 'Цветы и растения' },
  { code: 'vegetables', label: 'Овощи и фрукты' },
  { code: 'grocery', label: 'Продукты' },
  { code: 'bakery', label: 'Выпечка и кондитерка' },
  { code: 'clothing', label: 'Одежда' },
  { code: 'shoes', label: 'Обувь' },
  { code: 'electronics', label: 'Электроника' },
  { code: 'building', label: 'Стройматериалы' },
  { code: 'cosmetics', label: 'Косметика' },
  { code: 'auto', label: 'Автозапчасти' },
  { code: 'pets', label: 'Зоотовары' },
  { code: 'books', label: 'Книги' },
  { code: 'furniture', label: 'Мебель' },
  { code: 'handmade', label: 'Hand-made' },
  { code: 'services', label: 'Услуги' },
  { code: 'other', label: 'Другое' },
]

const EMPTY_FORM = {
  slug: '',
  name: '',
  category_preset: 'fish',
  plan_code: 'start',
  owner_phone: '',
  owner_name: '',
  owner_password: '',
}

export default function PlatformTenants() {
  const { toast } = useToast()
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [creating, setCreating] = useState(false)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)

  const params = new URLSearchParams({ limit: '100' })
  if (query.trim()) params.set('q', query.trim())
  if (status) params.set('status', status)
  const { data, loading, reload } = usePlatformApi<{ items: Tenant[]; total: number }>(`/tenants?${params}`)
  const { data: catalog } = usePlatformApi<PlatformCatalog>('/catalog')

  const create = async () => {
    if (!/^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$/.test(form.slug.trim())) {
      return toast('Адрес: латиница, цифры и дефис, от 3 до 63 символов', 'error')
    }
    if (form.name.trim().length < 2) return toast('Укажите название магазина', 'error')
    setBusy(true)
    try {
      await platformApi('/tenants', {
        method: 'POST',
        body: {
          slug: form.slug.trim().toLowerCase(),
          name: form.name.trim(),
          category_preset: form.category_preset,
          plan_code: form.plan_code,
          owner_phone: form.owner_phone.trim() || null,
          owner_name: form.owner_name.trim(),
          owner_password: form.owner_password.trim() || null,
        },
      })
      toast('Магазин создан. Домен и владелец подключены.')
      setCreating(false)
      setForm(EMPTY_FORM)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось создать магазин', 'error')
    } finally {
      setBusy(false)
    }
  }

  const setStatusFor = async (tenant: Tenant, value: string) => {
    try {
      await platformApi(`/tenants/${tenant.id}`, { method: 'PATCH', body: { status: value } })
      toast(`Статус «${tenant.name}»: ${STATUS_LABEL[value] ?? value}`)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить статус', 'error')
    }
  }

  return (
    <div className="platform-page">
      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Магазины</h2>
            <p className="muted">Арендаторы, их домены, тарифы и состояние.</p>
          </div>
          <button type="button" className="btn btn--sm btn--primary" onClick={() => setCreating(true)}>
            Добавить магазин
          </button>
        </div>

        <div className="platform-filters">
          <input
            className="input input--sm"
            placeholder="Поиск по названию или адресу"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <select className="input input--sm input--select" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">Все статусы</option>
            {Object.entries(STATUS_LABEL).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>

        <div className="platform-table-wrap">
          <table className="platform-table">
            <thead>
              <tr><th>Магазин</th><th>Основной домен</th><th>Тариф</th><th>Статус</th><th /></tr>
            </thead>
            <tbody>
              {loading && <tr><td colSpan={5} className="muted">Загрузка…</td></tr>}
              {!loading && (data?.items ?? []).map((tenant) => (
                <tr key={tenant.id}>
                  <td>
                    <Link to={`/platform/tenants/${tenant.id}`}><strong>{tenant.name}</strong></Link>
                    <span className="muted"> /{tenant.slug}</span>
                    {tenant.is_demo && <span className="badge badge--gold">демо</span>}
                  </td>
                  <td>{tenant.domains.find((item) => item.is_primary)?.host ?? '—'}</td>
                  <td>{catalog?.plans.find((plan) => plan.code === tenant.plan_code)?.title ?? tenant.plan_code}</td>
                  <td>
                    <select
                      className="input input--sm input--select"
                      value={tenant.status}
                      onChange={(event) => void setStatusFor(tenant, event.target.value)}
                    >
                      {Object.entries(STATUS_LABEL).map(([value, label]) => (
                        <option key={value} value={value}>{label}</option>
                      ))}
                    </select>
                  </td>
                  <td><Link className="btn btn--sm btn--ghost" to={`/platform/tenants/${tenant.id}`}>Управлять</Link></td>
                </tr>
              ))}
              {!loading && !data?.items.length && (
                <tr><td colSpan={5} className="muted">Ничего не найдено.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {creating && (
        <Modal
          title="Новый магазин"
          subtitle="Создаём арендатора, поддомен, владельца и подписку."
          onClose={() => setCreating(false)}
          footer={(
            <>
              <button type="button" className="btn btn--ghost" onClick={() => setCreating(false)}>Отмена</button>
              <button type="button" className="btn btn--primary" disabled={busy} onClick={() => void create()}>
                {busy ? 'Создаём…' : 'Создать магазин'}
              </button>
            </>
          )}
        >
          <div className="platform-form">
            <label className="field">
              <span className="field__label">Название</span>
              <input className="input" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Цветочная лавка" />
            </label>
            <label className="field">
              <span className="field__label">Адрес на платформе</span>
              <input className="input" value={form.slug} onChange={(event) => setForm({ ...form, slug: event.target.value.toLowerCase() })} placeholder="flowers" />
              <span className="field__hint">Будет доступен как {form.slug || 'slug'}.platform.by</span>
            </label>
            <label className="field">
              <span className="field__label">Категория</span>
              <select className="input input--select" value={form.category_preset} onChange={(event) => setForm({ ...form, category_preset: event.target.value })}>
                {PRESETS.map((preset) => <option key={preset.code} value={preset.code}>{preset.label}</option>)}
              </select>
            </label>
            <label className="field">
              <span className="field__label">Тариф</span>
              <select className="input input--select" value={form.plan_code} onChange={(event) => setForm({ ...form, plan_code: event.target.value })}>
                {(catalog?.plans ?? []).map((plan) => (
                  <option key={plan.code} value={plan.code}>{plan.title} — {plan.price_month.toFixed(2)} BYN/мес</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field__label">Телефон владельца</span>
              <input className="input" value={form.owner_phone} onChange={(event) => setForm({ ...form, owner_phone: event.target.value })} placeholder="+375 29 123-45-67" />
            </label>
            <label className="field">
              <span className="field__label">Имя владельца</span>
              <input className="input" value={form.owner_name} onChange={(event) => setForm({ ...form, owner_name: event.target.value })} placeholder="Иван" />
            </label>
            <label className="field">
              <span className="field__label">Пароль владельца</span>
              <input className="input" type="password" value={form.owner_password} onChange={(event) => setForm({ ...form, owner_password: event.target.value })} placeholder="Минимум 8 символов" />
              <span className="field__hint">Обязателен, если указан телефон владельца.</span>
            </label>
          </div>
        </Modal>
      )}
    </div>
  )
}
