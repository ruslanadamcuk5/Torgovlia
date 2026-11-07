import { useEffect, useState } from 'react'
import { platformApi, usePlatformApi } from '../../lib/platformApi'
import { useToast } from '../../store/ToastContext'
import { humanDate } from '../../lib/format'
import type { PlatformSettings as Settings } from '../../lib/types'

const PLAN_LABEL: Record<string, string> = {
  start: 'Старт',
  business: 'Бизнес',
  pro: 'Про',
}

export default function PlatformSettings() {
  const { toast } = useToast()
  const { data, loading, reload } = usePlatformApi<Settings>('/settings')
  const [form, setForm] = useState<Settings | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (data) setForm(data)
  }, [data])

  const patch = (changes: Partial<Settings>) => {
    setForm((current) => (current ? { ...current, ...changes } : current))
  }

  const save = async () => {
    if (!form) return
    if (form.brand_name.trim().length < 2) {
      toast('Название бренда слишком короткое', 'error')
      return
    }
    setSaving(true)
    try {
      await platformApi('/settings', {
        method: 'PATCH',
        body: {
          brand_name: form.brand_name.trim(),
          support_email: form.support_email.trim(),
          support_phone: form.support_phone.trim(),
          default_plan_code: form.default_plan_code,
          allow_signups: form.allow_signups,
          max_tenants: Number(form.max_tenants) || 0,
          maintenance_notice: form.maintenance_notice.trim(),
          payment_instructions: form.payment_instructions.trim(),
          sms_sender: form.sms_sender.trim(),
        },
      })
      toast('Настройки сохранены')
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить настройки', 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading || !form) return <div className="loader-block">Загружаем настройки…</div>

  return (
    <div className="platform-page">
      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Бренд и контакты</h2>
            <p className="muted">Название видно на статус-странице и в письмах платформы.</p>
          </div>
          <span className="badge badge--muted">{form.updated_at ? `Изменено ${humanDate(form.updated_at)}` : 'По умолчанию'}</span>
        </div>
        <div className="settings-grid">
          <label className="settings-field">
            <span>Название платформы</span>
            <input className="input input--sm" value={form.brand_name} maxLength={80} onChange={(event) => patch({ brand_name: event.target.value })} />
          </label>
          <label className="settings-field">
            <span>Email поддержки</span>
            <input className="input input--sm" type="email" value={form.support_email} onChange={(event) => patch({ support_email: event.target.value })} />
          </label>
          <label className="settings-field">
            <span>Телефон поддержки</span>
            <input className="input input--sm" value={form.support_phone} placeholder="+375 ..." onChange={(event) => patch({ support_phone: event.target.value })} />
          </label>
          <label className="settings-field">
            <span>SMS-подпись</span>
            <input className="input input--sm" value={form.sms_sender} maxLength={40} onChange={(event) => patch({ sms_sender: event.target.value })} />
          </label>
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Набор магазинов и лимиты</h2>
            <p className="muted">Режим набора действует на публичную форму регистрации.</p>
          </div>
        </div>
        <div className="settings-grid">
          <label className="settings-field">
            <span>Тариф по умолчанию</span>
            <select className="input input--sm input--select" value={form.default_plan_code} onChange={(event) => patch({ default_plan_code: event.target.value })}>
              {Object.entries(PLAN_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="settings-field">
            <span>Максимум магазинов</span>
            <input className="input input--sm" type="number" min={0} max={100000} value={form.max_tenants} onChange={(event) => patch({ max_tenants: Number(event.target.value) })} />
            <small className="muted">0 — без ограничения</small>
          </label>
          <label className="settings-check">
            <input type="checkbox" checked={form.allow_signups} onChange={(event) => patch({ allow_signups: event.target.checked })} />
            <span>
              <strong>Принимать новые магазины</strong>
              <small className="muted">Если выключить, форма регистрации покажет сообщение поддержки.</small>
            </span>
          </label>
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Платежи и объявления</h2>
            <p className="muted">Инструкция показывается в счетах, объявление — на статус-странице.</p>
          </div>
        </div>
        <div className="settings-grid settings-grid--single">
          <label className="settings-field">
            <span>Инструкция по оплате</span>
            <textarea className="input input--sm settings-textarea" value={form.payment_instructions} maxLength={3000} onChange={(event) => patch({ payment_instructions: event.target.value })} />
          </label>
          <label className="settings-field">
            <span>Объявление на статус-странице</span>
            <textarea className="input input--sm settings-textarea" value={form.maintenance_notice} maxLength={500} placeholder="Например: в воскресенье с 2:00 до 4:00 — плановые работы." onChange={(event) => patch({ maintenance_notice: event.target.value })} />
          </label>
        </div>
      </section>

      <div className="settings-actions">
        <button type="button" className="btn btn--primary" disabled={saving} onClick={() => void save()}>
          {saving ? 'Сохраняем…' : 'Сохранить настройки'}
        </button>
      </div>
    </div>
  )
}
