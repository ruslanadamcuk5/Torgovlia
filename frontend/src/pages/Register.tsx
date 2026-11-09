import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authApi, assetUrl } from '../lib/api'
import { useAuth } from '../store/AuthContext'
import { useSite } from '../store/SettingsContext'
import { useToast } from '../store/ToastContext'
import { SmsVerify } from '../components/SmsVerify'
import { Spinner } from '../components/ui'
import { Icon } from '../components/icons'
import { normalizePhoneInput, phonePretty, samePhone } from '../lib/format'

export default function Register() {
  const { setSession } = useAuth()
  const { site } = useSite()
  const { toast } = useToast()
  const navigate = useNavigate()

  const [fullName, setFullName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordRepeat, setPasswordRepeat] = useState('')
  const [consent, setConsent] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [phoneToken, setPhoneToken] = useState('')
  const [verifiedPhone, setVerifiedPhone] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async () => {
    setError('')
    if (fullName.trim().length < 2) return setError('Укажите имя')
    if (!phoneToken || !samePhone(verifiedPhone, phone)) return setError('Подтвердите номер телефона кодом из SMS')
    if (password.length < 8) return setError('Пароль должен содержать минимум 8 символов')
    if (!/[A-Za-zА-Яа-я]/.test(password) || !/\d/.test(password)) return setError('Пароль должен содержать буквы и цифры')
    if (password !== passwordRepeat) return setError('Пароли не совпадают')
    if (!consent) return setError('Необходимо согласие на обработку персональных данных')

    setBusy(true)
    try {
      const data = await authApi.register({
        phone_token: phoneToken,
        password,
        full_name: fullName.trim(),
        email: email.trim() || undefined,
        consent_personal_data: consent,
      })
      setSession(data)
      toast('Аккаунт создан. Добро пожаловать!')
      navigate('/account', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось зарегистрироваться')
    } finally {
      setBusy(false)
    }
  }

  if (!site) return null
  const s = site.settings
  const phoneVerified = Boolean(phoneToken) && samePhone(verifiedPhone, phone)

  return (
    <div className="auth-page">
      <div className="auth-shell">
        <aside className="auth-aside auth-aside--register">
          <Link to="/" className="auth-aside__brand">
            <img src={assetUrl(s.logo_url)} alt="" width={48} height={48} />
            <span><strong>{s.brand_name}</strong><span>{s.city} · {s.market_name}</span></span>
          </Link>
          <div className="auth-aside__content">
            <span className="eyebrow eyebrow--light">Регистрация</span>
            <h1>Заказывайте быстрее</h1>
            <p>Подтверждение номера по SMS — обязательное требование при оформлении заказов. Так мы защищаем ваши заказы.</p>
            <ul>
              <li><Icon name="shield" size={18} /> Номер подтверждается кодом из SMS</li>
              <li><Icon name="clock" size={18} /> История и повтор заказов</li>
              <li><Icon name="wallet" size={18} /> Без предоплаты, оплата при получении</li>
            </ul>
          </div>
          <div className="auth-aside__foot"><Icon name="pin" size={17} /> {s.address}</div>
        </aside>

        <div className="auth-card">
          <div className="auth-card__head">
            <h2>Создать аккаунт</h2>
            <p>Достаточно имени, телефона и пароля.</p>
          </div>

          <label className="field">
            <span className="field__label">Имя *</span>
            <input className="input" value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="Как к вам обращаться" autoComplete="name" />
          </label>

          <label className="field">
            <span className="field__label">Мобильный телефон *</span>
            <input
              className="input"
              value={phone}
              onChange={(event) => {
                setPhone(normalizePhoneInput(event.target.value))
                setPhoneToken('')
                setVerifiedPhone('')
              }}
              onBlur={() => setPhone((value) => phonePretty(value))}
              placeholder="+375 29 123-45-67"
              inputMode="tel"
              autoComplete="tel"
            />
          </label>

          {phoneVerified ? (
            <div className="verified-account"><Icon name="check" size={18} /> Номер {phonePretty(verifiedPhone)} подтверждён</div>
          ) : (
            <SmsVerify
              key={phone}
              phone={phone}
              purpose="register"
              onVerified={(token, verified) => { setPhoneToken(token); setVerifiedPhone(verified) }}
            />
          )}

          <label className="field">
            <span className="field__label">E-mail (необязательно)</span>
            <input className="input" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="mail@example.com" autoComplete="email" />
          </label>

          <div className="form-grid">
            <label className="field">
              <span className="field__label">Пароль *</span>
              <span className="input-wrap">
                <input
                  className="input"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Минимум 8 символов"
                  autoComplete="new-password"
                />
                <button type="button" className="input-wrap__btn" onClick={() => setShowPassword((value) => !value)} aria-label="Показать пароль">
                  <Icon name={showPassword ? 'eye-off' : 'eye'} size={18} />
                </button>
              </span>
            </label>
            <label className="field">
              <span className="field__label">Повторите пароль *</span>
              <input
                className="input"
                type={showPassword ? 'text' : 'password'}
                value={passwordRepeat}
                onChange={(event) => setPasswordRepeat(event.target.value)}
                placeholder="Ещё раз"
                autoComplete="new-password"
              />
            </label>
          </div>
          <span className="field__hint">Пароль должен содержать буквы и цифры, не менее 8 символов.</span>

          <label className="checkbox">
            <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
            <span>
              Я согласен(-на) на обработку персональных данных в соответствии с{' '}
              <Link to="/legal/privacy" target="_blank">политикой</Link> и принимаю{' '}
              <Link to="/legal/offer" target="_blank">правила оформления заказов</Link>.
            </span>
          </label>

          {error && <div className="notice notice--error"><Icon name="alert" size={17} /><span>{error}</span></div>}

          <button type="button" className="btn btn--primary btn--lg btn--block" onClick={submit} disabled={busy}>
            {busy ? <Spinner size={18} /> : 'Создать аккаунт'}
          </button>

          <div className="auth-register">
            <span>Уже есть аккаунт?</span>
            <Link to="/login" className="btn btn--outline btn--block">Войти</Link>
          </div>
        </div>
      </div>
    </div>
  )
}
