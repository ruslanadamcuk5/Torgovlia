import { useState } from 'react'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Icon, type IconName } from '../../components/icons'
import { Loader } from '../../components/ui'
import { formatMoney, humanDate } from '../../lib/format'
import type { BillingOverview } from '../../lib/types'

const STATUS_LABEL: Record<string, string> = {
  draft: 'Черновик',
  open: 'К оплате',
  paid: 'Оплачен',
  canceled: 'Отменён',
}

const KIND_LABEL: Record<string, string> = {
  subscription: 'Подписка',
  plan_change: 'Смена тарифа',
  addon: 'Сервис',
  manual: 'Прочее',
}

const METHOD_ICONS: Record<string, IconName> = {
  wallet: 'wallet',
  card: 'wallet',
  receipt: 'list',
}

const STATUS_BADGE: Record<string, string> = {
  open: 'badge--gold',
  paid: 'badge--fresh',
  canceled: 'badge--muted',
  draft: 'badge--muted',
}

export default function AdminBilling() {
  const { toast } = useToast()
  const { data, loading, error, reload } = useApi<BillingOverview>('/admin/billing')
  const [busy, setBusy] = useState<string | null>(null)

  const changePlan = async (code: string) => {
    setBusy(code)
    try {
      const result = await api<{
        applied: boolean
        plan_code: string
        pending_plan_code?: string
        invoice?: { number: string; amount: number }
      }>('/admin/billing/plan', { method: 'POST', body: { plan_code: code } })
      if (result.applied) {
        toast('Тариф изменён')
      } else if (result.invoice) {
        toast(`Счёт ${result.invoice.number} на ${formatMoney(result.invoice.amount)} BYN создан. После оплаты тариф включится автоматически.`)
      } else {
        toast('Заявка на смену тарифа принята')
      }
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сменить тариф', 'error')
    } finally {
      setBusy(null)
    }
  }

  if (loading) return <Loader label="Загружаем оплату" />
  if (error) {
    return (
      <div className="empty-state">
        <div className="empty-state__icon"><Icon name="alert" size={26} /></div>
        <h3>Не удалось загрузить биллинг</h3>
        <p>{error}</p>
        <button type="button" className="btn btn--primary" onClick={reload}>Повторить</button>
      </div>
    )
  }

  const invoices = data?.invoices ?? []

  return (
    <div className="billing-page">
      <section className="panel billing-summary">
        <div>
          <span className="muted">Текущий тариф</span>
          <strong>{data?.plan_title ?? '—'}</strong>
          <small className="muted">{formatMoney(data?.price_month ?? 0)} BYN / месяц</small>
        </div>
        <div>
          <span className="muted">Подписка</span>
          <strong>{data?.subscription_status === 'trial' ? 'Пробный период' : 'Активна'}</strong>
          <small className="muted">{data?.period_end ? `до ${humanDate(data.period_end)}` : 'бессрочно'}</small>
        </div>
        <div>
          <span className="muted">К оплате</span>
          <strong>{formatMoney(data?.open_invoices_total ?? 0)} BYN</strong>
          <small className="muted">{invoices.filter((item) => item.status === 'open').length} счёт(ов)</small>
        </div>
      </section>

      {data?.pending_plan_code && (
        <div className="billing-notice">
          <Icon name="clock" size={18} />
          <div>
            <strong>Ожидает оплаты: тариф «{data.plans.find((plan) => plan.code === data.pending_plan_code)?.title ?? data.pending_plan_code}»</strong>
            <span>Оплатите счёт ниже — тариф и сервисы включатся автоматически.</span>
          </div>
        </div>
      )}

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Тарифы</h2>
            <p className="muted">Повышение тарифа — после оплаты счёта. Понижение — сразу.</p>
          </div>
        </div>
        <div className="billing-plans">
          {(data?.plans ?? []).map((plan) => {
            const current = plan.code === data?.plan_code
            return (
              <article key={plan.code} className={`billing-plan ${current ? 'is-current' : ''}`}>
                <header>
                  <h3>{plan.title}</h3>
                  {current && <span className="badge badge--fresh">текущий</span>}
                </header>
                <strong>{formatMoney(plan.price_month)} BYN <small>/ мес</small></strong>
                <p>{plan.description}</p>
                <ul>
                  <li>Товаров: {plan.quotas.products ? plan.quotas.products : 'без лимита'}</li>
                  <li>Хранилище: {plan.quotas.storage_gb} ГБ</li>
                  <li>SMS: {plan.quotas.sms_month} / мес</li>
                  <li>Сотрудников: {plan.quotas.users}</li>
                </ul>
                <button
                  type="button"
                  className={`btn btn--sm ${current ? 'btn--ghost' : 'btn--primary'}`}
                  disabled={current || busy === plan.code}
                  onClick={() => void changePlan(plan.code)}
                >
                  {busy === plan.code ? 'Сохраняем…' : current ? 'Подключён' : 'Перейти'}
                </button>
              </article>
            )
          })}
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Способы оплаты</h2>
            <p className="muted">Доступные сейчас и подключаемые способы. Все платежи подтверждаются в панели платформы.</p>
          </div>
        </div>
        <div className="billing-methods">
          {(data?.payment_methods ?? []).map((method) => (
            <article key={method.code} className={`billing-method ${method.status === 'available' ? 'is-available' : ''}`}>
              <header>
                <span className="billing-method__icon"><Icon name={METHOD_ICONS[method.icon] ?? 'wallet'} size={18} /></span>
                <strong>{method.title}</strong>
                <span className={`badge ${method.status === 'available' ? 'badge--fresh' : 'badge--muted'}`}>
                  {method.status === 'available' ? 'Доступен' : 'Подключается'}
                </span>
              </header>
              <p>{method.description}</p>
              <small>{method.instructions}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="panel billing-howto">
        <h3>Как оплатить</h3>
        <ol>
          <li>Счёт формируется автоматически при смене тарифа или подключении платного сервиса.</li>
          <li>Переведите сумму по реквизитам платформы, указав номер счёта в назначении платежа.</li>
          <li>Платформа подтвердит оплату — тариф и сервисы включатся без повторных действий.</li>
        </ol>
        <p className="muted">
          Нужна оплата картой или через ЕРИП? Напишите в поддержку платформы — подключим удобный способ.
        </p>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Счета</h2>
            <p className="muted">История начислений и подтверждённых оплат.</p>
          </div>
        </div>

        <div className="platform-table-wrap">
          <table className="platform-table">
            <thead>
              <tr><th>Номер</th><th>Назначение</th><th>Сумма</th><th>Создан</th><th>Статус</th></tr>
            </thead>
            <tbody>
              {invoices.map((item) => (
                <tr key={item.id}>
                  <td><strong>{item.number}</strong></td>
                  <td>
                    {item.description}
                    <span className="muted"> · {KIND_LABEL[item.kind] ?? item.kind}</span>
                  </td>
                  <td>{formatMoney(item.amount)} {item.currency}</td>
                  <td>{humanDate(item.created_at)}</td>
                  <td>
                    <span className={`badge ${STATUS_BADGE[item.status] ?? 'badge--muted'}`}>
                      {STATUS_LABEL[item.status] ?? item.status}
                    </span>
                  </td>
                </tr>
              ))}
              {!invoices.length && (
                <tr><td colSpan={5} className="muted">Счетов пока нет.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
