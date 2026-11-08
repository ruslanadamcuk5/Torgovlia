import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Loader, Spinner } from '../../components/ui'
import { Icon } from '../../components/icons'
import { formatMoney } from '../../lib/format'

interface Level {
  code: string
  title: string
  threshold: number
  multiplier: number
}

interface LoyaltySettings {
  is_active: boolean
  earn_per_byn: number
  point_value: number
  max_redeem_percent: number
  min_redeem_points: number
  levels: Level[]
}

interface LevelInfo {
  code: string
  title: string
  multiplier: number
  threshold: number
  next: { code: string; title: string; threshold: number; multiplier: number; remaining: number } | null
}

interface Account {
  id: number
  name: string
  phone: string
  phone_raw: string
  balance: number
  earned_total: number
  spent_total: number
  level: string
  level_info: LevelInfo
  updated_at: string
}

interface Overview {
  settings: LoyaltySettings
  summary: {
    accounts: number
    balance: number
    earned: number
    spent: number
    levels: Record<string, number>
  }
  items: Account[]
}

interface Transaction {
  id: number
  kind: string
  points: number
  balance_after: number
  note: string
  order_number: string
  actor: string
  created_at: string
}

const KIND_LABEL: Record<string, string> = {
  earn: 'Начисление',
  redeem: 'Списание',
  refund: 'Возврат',
  adjust: 'Корректировка',
}

const LEVEL_TONE: Record<string, string> = {
  bronze: 'bronze',
  silver: 'silver',
  gold: 'gold',
}

function pointsMoney(points: number, value: number): string {
  return formatMoney(points * value)
}

export default function Loyalty() {
  const { toast } = useToast()
  const { data: features, loading: featuresLoading } = useApi<{ services: Record<string, boolean> }>(
    '/admin/services/features',
  )
  const enabled = Boolean(features?.services.loyalty)
  const { data, loading, reload } = useApi<Overview>(enabled ? '/admin/loyalty?limit=200' : null)

  const [search, setSearch] = useState('')
  const [form, setForm] = useState<LoyaltySettings | null>(null)
  const [saving, setSaving] = useState(false)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [history, setHistory] = useState<Record<number, Transaction[]>>({})
  const [adjusting, setAdjusting] = useState<Account | null>(null)
  const [adjustPoints, setAdjustPoints] = useState('')
  const [adjustNote, setAdjustNote] = useState('')
  const [adjustBusy, setAdjustBusy] = useState(false)

  useEffect(() => {
    if (data?.settings) setForm(data.settings)
  }, [data?.settings])

  const settings = form ?? data?.settings ?? null
  const pointValue = settings?.point_value ?? 0.01
  const accounts = useMemo(() => {
    const query = search.trim().toLowerCase()
    return (data?.items ?? []).filter(
      (item) =>
        !query ||
        item.phone_raw.includes(query) ||
        item.phone.toLowerCase().includes(query) ||
        item.name.toLowerCase().includes(query),
    )
  }, [data, search])

  const saveSettings = async () => {
    if (!settings) return
    setSaving(true)
    try {
      const result = await api<{ settings: LoyaltySettings }>('/admin/loyalty/settings', {
        method: 'PUT',
        body: {
          is_active: settings.is_active,
          earn_per_byn: settings.earn_per_byn,
          point_value: settings.point_value,
          max_redeem_percent: settings.max_redeem_percent,
          min_redeem_points: settings.min_redeem_points,
        },
      })
      setForm(result.settings)
      reload()
      toast('Настройки бонусной программы сохранены')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить настройки', 'error')
    } finally {
      setSaving(false)
    }
  }

  const loadHistory = async (account: Account) => {
    try {
      const result = await api<{ items: Transaction[] }>(
        `/admin/loyalty/accounts/${account.id}/transactions?limit=100`,
      )
      setHistory((current) => ({ ...current, [account.id]: result.items }))
    } catch {
      toast('Не удалось загрузить историю баллов', 'error')
    }
  }

  const toggleAccount = (account: Account) => {
    const next = expanded === account.id ? null : account.id
    setExpanded(next)
    if (next && !history[next]) void loadHistory(account)
  }

  const openAdjust = (account: Account) => {
    setAdjusting(account)
    setAdjustPoints('')
    setAdjustNote('')
  }

  const submitAdjust = async () => {
    if (!adjusting) return
    const points = Number(adjustPoints)
    if (!Number.isFinite(points) || points === 0) {
      toast('Укажите количество баллов: плюс начислить, минус списать', 'error')
      return
    }
    setAdjustBusy(true)
    try {
      await api<Account>(`/admin/loyalty/accounts/${adjusting.id}/adjust`, {
        method: 'POST',
        body: { points: Math.trunc(points), note: adjustNote.trim() },
      })
      reload()
      if (expanded === adjusting.id) void loadHistory(adjusting)
      toast(points > 0 ? `Начислено ${points} баллов` : `Списано ${Math.abs(points)} баллов`)
      setAdjusting(null)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить баланс', 'error')
    } finally {
      setAdjustBusy(false)
    }
  }

  if (featuresLoading) return <Loader />

  if (!enabled) {
    return (
      <div className="admin-page">
        <section className="panel panel--accent">
          <div className="panel__head"><h2>Бонусная программа</h2></div>
          <p>
            Баллы, уровни и списание доступны на тарифе <strong>«Про»</strong>. Покупатели
            получают баллы за полученные заказы и платят ими до 30% следующей покупки.
          </p>
          <Link to="/admin/services" className="btn btn--primary">
            Перейти к сервисам <Icon name="arrow-right" size={17} />
          </Link>
        </section>
      </div>
    )
  }

  return (
    <div className="admin-page loyalty-page">
      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Бонусная программа</h2>
            <p className="muted">
              Баллы начисляются за полученные заказы и списываются при оформлении.
              Уровень растёт вместе с накопленными баллами и даёт множитель.
            </p>
          </div>
          {settings && (
            <label className="loyalty-toggle">
              <input
                type="checkbox"
                checked={settings.is_active}
                onChange={(event) => setForm({ ...settings, is_active: event.target.checked })}
              />
              <span>{settings.is_active ? 'Программа включена' : 'Программа выключена'}</span>
            </label>
          )}
        </div>

        {settings && (
          <>
            <div className="loyalty-grid">
              <label className="field">
                <span className="field__label">Баллов за 1 BYN</span>
                <input
                  className="input"
                  type="number"
                  min={0}
                  max={100}
                  value={settings.earn_per_byn}
                  onChange={(event) => setForm({ ...settings, earn_per_byn: Number(event.target.value) })}
                />
                <span className="field__hint">Заказ на 100 BYN принесёт {Math.round(100 * settings.earn_per_byn)} баллов</span>
              </label>
              <label className="field">
                <span className="field__label">Стоимость 1 балла, BYN</span>
                <input
                  className="input"
                  type="number"
                  min={0.001}
                  max={1}
                  step={0.001}
                  value={settings.point_value}
                  onChange={(event) => setForm({ ...settings, point_value: Number(event.target.value) })}
                />
                <span className="field__hint">100 баллов = {formatMoney(100 * settings.point_value)}</span>
              </label>
              <label className="field">
                <span className="field__label">Списание, % суммы</span>
                <input
                  className="input"
                  type="number"
                  min={0}
                  max={100}
                  value={settings.max_redeem_percent}
                  onChange={(event) => setForm({ ...settings, max_redeem_percent: Number(event.target.value) })}
                />
                <span className="field__hint">Не больше {settings.max_redeem_percent}% суммы заказа</span>
              </label>
              <label className="field">
                <span className="field__label">Минимум для списания</span>
                <input
                  className="input"
                  type="number"
                  min={0}
                  max={100000}
                  value={settings.min_redeem_points}
                  onChange={(event) => setForm({ ...settings, min_redeem_points: Number(event.target.value) })}
                />
                <span className="field__hint">Например, 100 баллов</span>
              </label>
            </div>

            <div className="loyalty-levels">
              {settings.levels.map((level) => (
                <div className={`loyalty-level loyalty-level--${LEVEL_TONE[level.code] ?? 'bronze'}`} key={level.code}>
                  <Icon name="gift" size={16} />
                  <div>
                    <strong>{level.title}</strong>
                    <small>
                      {level.threshold > 0 ? `от ${level.threshold} баллов` : 'с первого заказа'}
                      {' · '}×{level.multiplier.toLocaleString('ru-BY')}
                    </small>
                  </div>
                </div>
              ))}
            </div>

            <div className="loyalty-actions">
              <button type="button" className="btn btn--primary" onClick={saveSettings} disabled={saving}>
                {saving ? <Spinner /> : <Icon name="check" size={16} />} Сохранить настройки
              </button>
              <span className="muted">
                Изменения правил применяются к новым заказам, уже начисленные баллы не пересчитываются.
              </span>
            </div>
          </>
        )}
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h3>Бонусные счета</h3>
            <p className="muted">Баланс, уровень и ручные корректировки по каждому покупателю.</p>
          </div>
          <div className="loyalty-search">
            <Icon name="search" size={16} />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Телефон или имя"
              maxLength={80}
            />
          </div>
        </div>

        <div className="loyalty-stats">
          <div><span>Счетов</span><strong>{data?.summary.accounts ?? 0}</strong></div>
          <div><span>На руках</span><strong>{data?.summary.balance ?? 0}</strong><small>{pointsMoney(data?.summary.balance ?? 0, pointValue)}</small></div>
          <div><span>Начислено</span><strong>{data?.summary.earned ?? 0}</strong></div>
          <div><span>Списано</span><strong>{data?.summary.spent ?? 0}</strong></div>
        </div>

        {loading && <p className="muted">Загружаем счета…</p>}

        <div className="loyalty-list">
          {accounts.map((account) => (
            <div className="loyalty-account" key={account.id}>
              <div className="loyalty-account__row">
                <span className={`loyalty-badge loyalty-badge--${LEVEL_TONE[account.level] ?? 'bronze'}`}>
                  {account.level_info.title}
                </span>
                <div className="loyalty-account__main">
                  <strong>{account.name}</strong>
                  <small>{account.phone}</small>
                </div>
                <div className="loyalty-account__balance">
                  <strong>{account.balance} баллов</strong>
                  <small>{pointsMoney(account.balance, pointValue)}</small>
                </div>
                <div className="loyalty-account__meta">
                  <span>начислено {account.earned_total}</span>
                  <span>списано {account.spent_total}</span>
                </div>
                <div className="loyalty-account__actions">
                  <button type="button" className="btn btn--sm btn--ghost" onClick={() => openAdjust(account)}>
                    <Icon name="wallet" size={15} /> Баллы
                  </button>
                  <button type="button" className="btn btn--sm btn--ghost" onClick={() => toggleAccount(account)}>
                    {expanded === account.id ? 'Скрыть' : 'История'}
                  </button>
                </div>
              </div>

              {account.level_info.next && (
                <div className="loyalty-progress">
                  <div className="loyalty-progress__bar">
                    <span
                      style={{
                        width: `${Math.min(100, Math.round((account.earned_total / account.level_info.next.threshold) * 100))}%`,
                      }}
                    />
                  </div>
                  <small>
                    До уровня «{account.level_info.next.title}» — {account.level_info.next.remaining} баллов
                  </small>
                </div>
              )}

              {expanded === account.id && (
                <div className="loyalty-history">
                  {(history[account.id] ?? []).map((row) => (
                    <div className="loyalty-history__row" key={row.id}>
                      <span className={`loyalty-history__kind loyalty-history__kind--${row.kind}`}>
                        {KIND_LABEL[row.kind] ?? row.kind}
                      </span>
                      <span className={row.points >= 0 ? 'is-plus' : 'is-minus'}>
                        {row.points >= 0 ? '+' : ''}{row.points}
                      </span>
                      <span className="loyalty-history__note">
                        {row.note}
                        {row.order_number ? ` · №${row.order_number}` : ''}
                      </span>
                      <span className="muted">{row.balance_after}</span>
                      <small>{new Date(row.created_at).toLocaleString('ru-BY')}</small>
                    </div>
                  ))}
                  {(history[account.id] ?? []).length === 0 && (
                    <p className="muted">Операций пока нет.</p>
                  )}
                </div>
              )}
            </div>
          ))}
          {!loading && accounts.length === 0 && (
            <div className="loyalty-empty">
              <Icon name="gift" size={22} />
              <p>
                {search
                  ? 'По запросу никого не нашли.'
                  : 'Бонусные счета появятся после первых полученных заказов или ручного начисления.'}
              </p>
            </div>
          )}
        </div>
      </section>

      {adjusting && (
        <div className="loyalty-modal" role="dialog" aria-modal="true">
          <div className="loyalty-modal__card">
            <div className="loyalty-modal__head">
              <h3>Баллы · {adjusting.name}</h3>
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => setAdjusting(null)}>
                <Icon name="close" size={16} />
              </button>
            </div>
            <p className="muted">
              Сейчас на счету {adjusting.balance} баллов ({pointsMoney(adjusting.balance, pointValue)}).
              Плюс — начислить, минус — списать.
            </p>
            <label className="field">
              <span className="field__label">Сколько баллов</span>
              <input
                className="input"
                type="number"
                value={adjustPoints}
                onChange={(event) => setAdjustPoints(event.target.value)}
                placeholder="Например, 500 или -200"
                autoFocus
              />
            </label>
            <label className="field">
              <span className="field__label">Причина</span>
              <input
                className="input"
                value={adjustNote}
                onChange={(event) => setAdjustNote(event.target.value)}
                maxLength={255}
                placeholder="Подарок, исправление, бонус за отзыв"
              />
            </label>
            <div className="loyalty-modal__actions">
              <button type="button" className="btn btn--ghost" onClick={() => setAdjusting(null)}>Отмена</button>
              <button type="button" className="btn btn--primary" onClick={submitAdjust} disabled={adjustBusy}>
                {adjustBusy ? <Spinner /> : <Icon name="check" size={16} />} Применить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
