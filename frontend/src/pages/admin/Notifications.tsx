import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Loader } from '../../components/ui'
import { Icon } from '../../components/icons'

interface NotificationSettings {
  notify_on_new_order: boolean
  notify_on_cancel: boolean
  notify_telegram_chat: string
  notify_sms_phone: string
  notify_email: string
}

interface NotificationData {
  settings: NotificationSettings
  channels: { telegram: boolean; sms: boolean; email: boolean }
}

const CHANNELS = [
  {
    key: 'telegram' as const,
    title: 'Telegram',
    icon: 'send' as const,
    hint: 'Бот платформы пришлёт сообщение в указанный чат. Чтобы узнать chat_id, напишите боту любое сообщение и откройте @userinfobot.',
    placeholder: 'например, 123456789 или -1001234567890',
  },
  {
    key: 'sms' as const,
    title: 'SMS',
    icon: 'smartphone' as const,
    hint: 'Короткое сообщение на телефон владельца. Доставка платная и работает при подключённом SMS-провайдере.',
    placeholder: '+375 29 111-22-33',
  },
  {
    key: 'email' as const,
    title: 'Email',
    icon: 'mail' as const,
    hint: 'Письмо на почту магазина. Работает, когда на платформе настроен SMTP.',
    placeholder: 'owner@example.by',
  },
]

export default function Notifications() {
  const { toast } = useToast()
  const { data, loading, reload } = useApi<NotificationData>('/admin/notifications')
  const [form, setForm] = useState<NotificationSettings | null>(null)
  const [busy, setBusy] = useState(false)
  const [testing, setTesting] = useState<string | null>(null)

  useEffect(() => {
    if (data?.settings) setForm({ ...data.settings })
  }, [data])

  if (loading || !form) return <Loader label="Загружаем настройки уведомлений…" />

  const set = <K extends keyof NotificationSettings>(key: K, value: NotificationSettings[K]) => {
    setForm((current) => (current ? { ...current, [key]: value } : current))
  }

  const save = async () => {
    setBusy(true)
    try {
      await api('/admin/notifications', { method: 'PUT', body: form })
      toast('Настройки уведомлений сохранены')
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить', 'error')
    } finally {
      setBusy(false)
    }
  }

  const test = async (channel: 'telegram' | 'sms' | 'email') => {
    const target = {
      telegram: form.notify_telegram_chat,
      sms: form.notify_sms_phone,
      email: form.notify_email,
    }[channel]
    setTesting(channel)
    try {
      await api('/admin/notifications/test', { method: 'POST', body: { channel, target } })
      toast('Тестовое уведомление отправлено')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось отправить тест', 'error')
    } finally {
      setTesting(null)
    }
  }

  return (
    <div className="admin-page notifications-page">
      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Уведомления о заказах</h2>
            <p className="muted">
              Магазин сообщит о новом заказе и отмене покупателем. Можно включить сразу несколько каналов —
              сообщения придут во все.
            </p>
          </div>
          <button type="button" className="btn btn--primary" onClick={save} disabled={busy}>
            {busy ? 'Сохраняем…' : 'Сохранить'}
          </button>
        </div>

        <div className="notify-events">
          <label className="notify-toggle">
            <input
              type="checkbox"
              checked={form.notify_on_new_order}
              onChange={(event) => set('notify_on_new_order', event.target.checked)}
            />
            <span>
              <b>Новый заказ</b>
              <small>Клиент оформил заказ — владелец сразу получает состав и время выдачи.</small>
            </span>
          </label>
          <label className="notify-toggle">
            <input
              type="checkbox"
              checked={form.notify_on_cancel}
              onChange={(event) => set('notify_on_cancel', event.target.checked)}
            />
            <span>
              <b>Отмена покупателем</b>
              <small>Покупатель отменил заказ — придёт отдельное сообщение.</small>
            </span>
          </label>
        </div>
      </section>

      <div className="notify-channels">
        {CHANNELS.map((channel) => {
          const configured = data?.channels[channel.key]
          const value = {
            telegram: form.notify_telegram_chat,
            sms: form.notify_sms_phone,
            email: form.notify_email,
          }[channel.key]
          return (
            <section className="panel notify-channel" key={channel.key}>
              <div className="panel__head">
                <h3><Icon name={channel.icon} size={18} /> {channel.title}</h3>
                <span className={`notify-state ${configured ? 'is-on' : ''}`}>
                  {configured ? 'Доступен' : 'Не настроен на платформе'}
                </span>
              </div>
              <label className="field">
                <span className="field__label">
                  {channel.key === 'telegram' ? 'Chat ID' : channel.key === 'sms' ? 'Телефон' : 'Адрес'}
                </span>
                <input
                  className="input"
                  value={value}
                  onChange={(event) =>
                    set(
                      channel.key === 'telegram'
                        ? 'notify_telegram_chat'
                        : channel.key === 'sms'
                          ? 'notify_sms_phone'
                          : 'notify_email',
                      event.target.value,
                    )
                  }
                  placeholder={channel.placeholder}
                />
              </label>
              <p className="field__hint">{channel.hint}</p>
              <div className="notify-actions">
                <button
                  type="button"
                  className="btn btn--sm btn--outline"
                  onClick={() => test(channel.key)}
                  disabled={testing === channel.key || !configured}
                >
                  <Icon name="send" size={15} />
                  {testing === channel.key ? 'Отправляем…' : 'Проверить'}
                </button>
              </div>
            </section>
          )
        })}
      </div>

      <section className="panel panel--soft">
        <h3>Что придёт в сообщении</h3>
        <pre className="notify-sample">{`🛒 Новый заказ RL-261108-1234
Сумма: 76,10 BYN
Клиент: Анна, +375 (29) 111-22-33
Когда: 09.11.2026 в 10:00 · доставка · Барановичи
Позиций: 2
Адрес: г. Барановичи, ул. Советская, 10`}</pre>
      </section>
    </div>
  )
}
