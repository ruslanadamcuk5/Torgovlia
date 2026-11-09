import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useSite } from '../store/SettingsContext'
import { useAuth } from '../store/AuthContext'
import { useToast } from '../store/ToastContext'
import { api } from '../lib/api'
import { useApi } from '../lib/useApi'
import { Icon } from '../components/icons'
import { Spinner } from '../components/ui'
import { formatMoney } from '../lib/format'

const PRESETS = [50, 75, 100, 150, 200]

type RequestForm = {
  amount: string
  recipient_name: string
  recipient_phone: string
  recipient_email: string
  sender_name: string
  sender_phone: string
  message: string
  consent: boolean
}

const EMPTY: RequestForm = {
  amount: '100',
  recipient_name: '',
  recipient_phone: '',
  recipient_email: '',
  sender_name: '',
  sender_phone: '',
  message: '',
  consent: false,
}

type CheckResult = {
  code: string
  status_label: string
  balance: number
  amount: number
  expires_at: string | null
  recipient_name: string
}

export default function GiftCertificates() {
  const { site } = useSite()
  const { user } = useAuth()
  const { toast } = useToast()
  const [form, setForm] = useState<RequestForm>(EMPTY)
  const [busy, setBusy] = useState(false)
  const [created, setCreated] = useState<{ code: string; amount: number; status_label: string; message: string } | null>(null)
  const [checkCode, setCheckCode] = useState('')
  const [checkBusy, setCheckBusy] = useState(false)
  const [checked, setChecked] = useState<CheckResult | null>(null)
  const [checkError, setCheckError] = useState('')

  const enabled = site?.features?.gift_certificates === true
  const { data: certificates } = useApi<{ items: { code: string; balance: number; status_label: string }[] }>(
    enabled && user ? '/gift-certificates/mine' : null,
    false,
  )

  if (!site) return null
  const s = site.settings

  if (!enabled) {
    return (
      <div className="container section">
        <div className="empty-state">
          <div className="empty-state__icon"><Icon name="gift" size={28} /></div>
          <h3>Подарочные сертификаты пока не подключены</h3>
          <p>Сервис можно включить в админке магазина в разделе «Сервисы».</p>
          <Link to="/catalog" className="btn btn--primary">В каталог</Link>
        </div>
      </div>
    )
  }

  const submit = async () => {
    const amount = Number(form.amount)
    if (!Number.isFinite(amount) || amount < 10) {
      toast('Минимальная сумма сертификата — 10 BYN', 'error')
      return
    }
    if (form.recipient_name.trim().length < 2) {
      toast('Укажите имя получателя', 'error')
      return
    }
    if (!form.recipient_phone.trim() && !form.recipient_email.trim()) {
      toast('Укажите телефон или email получателя', 'error')
      return
    }
    if (!form.consent) {
      toast('Нужно согласие на обработку персональных данных', 'error')
      return
    }
    setBusy(true)
    try {
      const result = await api<{ code: string; amount: number; status_label: string; message: string }>(
        '/gift-certificates/request',
        {
          method: 'POST',
          body: {
            amount,
            recipient_name: form.recipient_name.trim(),
            recipient_phone: form.recipient_phone.trim(),
            recipient_email: form.recipient_email.trim() || null,
            sender_name: form.sender_name.trim(),
            sender_phone: form.sender_phone.trim(),
            message: form.message.trim(),
            consent_personal_data: true,
          },
          auth: false,
        },
      )
      setCreated(result)
      setForm({ ...EMPTY, amount: form.amount })
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось создать сертификат', 'error')
    } finally {
      setBusy(false)
    }
  }

  const check = async () => {
    if (!checkCode.trim()) return
    setCheckBusy(true)
    setCheckError('')
    setChecked(null)
    try {
      const result = await api<CheckResult>('/gift-certificates/check', {
        method: 'POST',
        body: { code: checkCode.trim().toUpperCase() },
        auth: false,
      })
      setChecked(result)
    } catch (err) {
      setCheckError(err instanceof Error ? err.message : 'Сертификат не найден')
    } finally {
      setCheckBusy(false)
    }
  }

  return (
    <div className="gift-public">
      <section className="gift-hero">
        <div className="container gift-hero__inner">
          <div className="gift-hero__copy">
            <span className="eyebrow">Подарок, который точно подойдёт</span>
            <h1>Подарочный сертификат {s.brand_name}</h1>
            <p>
              Выберите сумму, подпишите открытку — получатель сам решит, что взять.
              Сертификат действует 12 месяцев и оплачивает любые товары магазина.
            </p>
            <div className="gift-hero__points">
              <span><Icon name="check" size={15} /> Любая сумма от 10 BYN</span>
              <span><Icon name="check" size={15} /> Код приходит после оплаты</span>
              <span><Icon name="check" size={15} /> Можно проверить баланс</span>
            </div>
          </div>
          <div className="gift-hero__card" aria-hidden="true">
            <div className="gift-card-visual">
              <span>{s.brand_name}</span>
              <strong>GIFT</strong>
              <small>подарочный сертификат</small>
            </div>
          </div>
        </div>
      </section>

      <div className="container section gift-public__grid">
        <section className="panel gift-public__form">
          {created ? (
            <div className="gift-created">
              <span className="gift-created__icon"><Icon name="check" size={28} /></span>
              <h2>Заявка создана</h2>
              <p>{created.message}</p>
              <div className="gift-created__code">
                <span>Код сертификата</span>
                <strong>{created.code}</strong>
              </div>
              <dl>
                <div><dt>Сумма</dt><dd>{formatMoney(created.amount)}</dd></div>
                <div><dt>Статус</dt><dd>{created.status_label}</dd></div>
              </dl>
              <p className="gift-created__hint">
                Покажите код администратору или позвоните по номеру {s.phone}, чтобы подтвердить оплату.
                После активации сертификат можно применить при оформлении заказа.
              </p>
              <button type="button" className="btn btn--outline" onClick={() => setCreated(null)}>
                Оформить ещё один
              </button>
            </div>
          ) : (
            <>
              <div className="panel__head">
                <div>
                  <h2>Оформить сертификат</h2>
                  <p className="muted">Оплата в магазине или по счёту. Код активируется после подтверждения.</p>
                </div>
              </div>
              <div className="gift-presets">
                {PRESETS.map((value) => (
                  <button
                    key={value}
                    type="button"
                    className={Number(form.amount) === value ? 'is-active' : ''}
                    onClick={() => setForm({ ...form, amount: String(value) })}
                  >
                    {value} BYN
                  </button>
                ))}
              </div>
              <label className="field">
                <span className="field__label">Своя сумма, BYN</span>
                <input className="input" type="number" min={10} max={1000} value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} />
              </label>
              <div className="gift-form__row">
                <label className="field">
                  <span className="field__label">Кому</span>
                  <input className="input" value={form.recipient_name} onChange={(event) => setForm({ ...form, recipient_name: event.target.value })} placeholder="Имя получателя" maxLength={120} />
                </label>
                <label className="field">
                  <span className="field__label">Телефон получателя</span>
                  <input className="input" value={form.recipient_phone} onChange={(event) => setForm({ ...form, recipient_phone: event.target.value })} placeholder="+375…" />
                </label>
              </div>
              <label className="field">
                <span className="field__label">Email получателя</span>
                <input className="input" type="email" value={form.recipient_email} onChange={(event) => setForm({ ...form, recipient_email: event.target.value })} placeholder="Если хотите отправить код письмом" />
              </label>
              <div className="gift-form__row">
                <label className="field">
                  <span className="field__label">От кого</span>
                  <input className="input" value={form.sender_name} onChange={(event) => setForm({ ...form, sender_name: event.target.value })} placeholder="Ваше имя" maxLength={120} />
                </label>
                <label className="field">
                  <span className="field__label">Ваш телефон</span>
                  <input className="input" value={form.sender_phone} onChange={(event) => setForm({ ...form, sender_phone: event.target.value })} placeholder="+375…" />
                </label>
              </div>
              <label className="field">
                <span className="field__label">Пожелание</span>
                <textarea className="textarea" rows={3} value={form.message} onChange={(event) => setForm({ ...form, message: event.target.value })} placeholder="Несколько тёплых слов — попадём на открытку" maxLength={400} />
              </label>
              <label className="gift-check">
                <input type="checkbox" checked={form.consent} onChange={(event) => setForm({ ...form, consent: event.target.checked })} />
                <span>
                  <strong>Согласен на обработку данных</strong>
                  <small>Телефон и email получателя нужны только для оформления сертификата.</small>
                </span>
              </label>
              <button type="button" className="btn btn--primary btn--lg btn--block" disabled={busy} onClick={() => void submit()}>
                {busy ? <Spinner size={18} /> : <Icon name="gift" size={18} />}
                {busy ? 'Создаём заявку…' : 'Оформить сертификат'}
              </button>
            </>
          )}
        </section>

        <aside className="gift-public__side">
          <section className="panel gift-check-panel">
            <div className="panel__head">
              <div>
                <h2>Проверить сертификат</h2>
                <p className="muted">Баланс и срок действия по коду.</p>
              </div>
            </div>
            <div className="gift-check__row">
              <input
                className="input"
                value={checkCode}
                onChange={(event) => setCheckCode(event.target.value.toUpperCase())}
                placeholder="GIFT-XXXX-XXXX"
                aria-label="Код сертификата"
              />
              <button type="button" className="btn btn--outline" disabled={checkBusy || !checkCode.trim()} onClick={() => void check()}>
                {checkBusy ? <Spinner size={15} /> : 'Проверить'}
              </button>
            </div>
            {checkError && <p className="gift-check__error">{checkError}</p>}
            {checked && (
              <div className="gift-check__result">
                <div>
                  <span>Доступно</span>
                  <strong>{formatMoney(checked.amount)}</strong>
                </div>
                <dl>
                  <div><dt>Баланс</dt><dd>{formatMoney(checked.balance)}</dd></div>
                  <div><dt>Действует до</dt><dd>{checked.expires_at ? new Date(checked.expires_at).toLocaleDateString('ru-BY') : 'бессрочно'}</dd></div>
                  {checked.recipient_name && <div><dt>Получатель</dt><dd>{checked.recipient_name}</dd></div>}
                </dl>
                <Link to="/cart" className="btn btn--primary btn--sm btn--block">Применить при заказе</Link>
              </div>
            )}
            <p className="gift-check__hint">
              Код вводится на странице оформления заказа в поле «Подарочный сертификат».
            </p>
          </section>

          {Boolean(certificates?.items.length) && (
            <section className="panel gift-my">
              <h2>Мои сертификаты</h2>
              {certificates?.items.map((cert) => (
                <button type="button" key={cert.code} onClick={() => setCheckCode(cert.code)}>
                  <span>{cert.code}</span>
                  <small>{cert.status_label}</small>
                  <b>{formatMoney(cert.balance)}</b>
                </button>
              ))}
            </section>
          )}

          <section className="panel gift-rules">
            <h2>Как это работает</h2>
            <ol>
              <li>Оформляете сертификат и оплачиваете удобным способом.</li>
              <li>Магазин активирует код и передаёт его получателю.</li>
              <li>Получатель выбирает товары и вводит код при оформлении.</li>
              <li>Если заказ отменён, сумма возвращается на сертификат.</li>
            </ol>
            <p>Вопросы — по телефону <a href={`tel:${s.phone.replace(/[^\d+]/g, '')}`}>{s.phone}</a>.</p>
          </section>
        </aside>
      </div>
    </div>
  )
}
