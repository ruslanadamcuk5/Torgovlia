import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { authApi, assetUrl } from '../lib/api'
import { useAuth } from '../store/AuthContext'
import { useSite } from '../store/SettingsContext'
import { useToast } from '../store/ToastContext'
import { SmsVerify } from '../components/SmsVerify'
import { Spinner } from '../components/ui'
import { Icon } from '../components/icons'
import { normalizePhoneInput, phonePretty } from '../lib/format'

export default function Login() {
  const { setSession, user } = useAuth()
  const { site } = useSite()
  const { toast } = useToast()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = params.get('next')
  const [mode, setMode] = useState<'password' | 'sms'>('password')
  const [phone, setPhone] = useState(user?.phone ?? '')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const goAfterLogin = (role: string) => {
    if (next) return navigate(next, { replace: true })
    if (role === 'admin') return navigate('/admin', { replace: true })
    if (role === 'seller') return navigate('/seller', { replace: true })
    return navigate('/account', { replace: true })
  }

  const submitPassword = async () => {
    setError('')
    setBusy(true)
    try {
      const data = await authApi.login(phone, password)
      setSession(data)
      toast(`Здравствуйте, ${data.user.full_name.split(' ')[0]}!`)
      goAfterLogin(data.user.role)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось войти')
    } finally {
      setBusy(false)
    }
  }

  const loginBySms = async (token: string) => {
    setBusy(true)
    setError('')
    try {
      const data = await authApi.loginByPhone(token)
      setSession(data)
      toast(`Здравствуйте, ${data.user.full_name.split(' ')[0]}!`)
      goAfterLogin(data.user.role)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось войти')
    } finally {
      setBusy(false)
    }
  }

  if (!site) return null
  const s = site.settings

  return (
    <div className="auth-page">
      <div className="auth-shell">
        <aside className="auth-aside">
          <Link to="/" className="auth-aside__brand">
            <img src={assetUrl(s.logo_url)} alt="" width={48} height={48} />
            <span><strong>{s.brand_name}</strong><span>{s.city} · {s.market_name}</span></span>
          </Link>
          <div className="auth-aside__content">
            <span className="eyebrow eyebrow--light">Личный кабинет</span>
            <h1>Ваши заказы всегда под рукой</h1>
            <p>История заказов, повтор заказа в один клик и статус сборки — в личном кабинете.</p>
            <ul>
              <li><Icon name="check" size={18} /> История заказов и статусы</li>
              <li><Icon name="check" size={18} /> Быстрое повторение заказа</li>
              <li><Icon name="check" size={18} /> Уведомления о готовности</li>
            </ul>
          </div>
          <div className="auth-aside__foot">
            <Icon name="pin" size={17} /> {s.city}, {s.market_name}, {s.pavilion}
          </div>
        </aside>

        <div className="auth-card">
          <div className="auth-card__head">
            <h2>Вход в аккаунт</h2>
            <p>Войдите, чтобы видеть историю заказов и повторять заказы.</p>
          </div>

          <div className="auth-tabs">
            <button type="button" className={mode === 'password' ? 'is-active' : ''} onClick={() => setMode('password')}>По паролю</button>
            <button type="button" className={mode === 'sms' ? 'is-active' : ''} onClick={() => setMode('sms')}>По SMS</button>
          </div>

          <label className="field">
            <span className="field__label">Мобильный телефон</span>
            <input
              className="input"
              value={phone}
              onChange={(event) => setPhone(normalizePhoneInput(event.target.value))}
              onBlur={() => setPhone((value) => phonePretty(value))}
              placeholder="+375 29 123-45-67"
              inputMode="tel"
              autoComplete="tel"
            />
          </label>

          {mode === 'password' ? (
            <>
              <label className="field">
                <span className="field__label">Пароль</span>
                <span className="input-wrap">
                  <input
                    className="input"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    onKeyDown={(event) => { if (event.key === 'Enter') void submitPassword() }}
                    placeholder="Ваш пароль"
                    autoComplete="current-password"
                  />
                  <button type="button" className="input-wrap__btn" onClick={() => setShowPassword((value) => !value)} aria-label="Показать пароль">
                    <Icon name={showPassword ? 'eye-off' : 'eye'} size={18} />
                  </button>
                </span>
              </label>
              <div className="auth-links">
                <Link to="/reset">Забыли пароль?</Link>
              </div>
              <button type="button" className="btn btn--primary btn--lg btn--block" onClick={submitPassword} disabled={busy}>
                {busy ? <Spinner size={18} /> : 'Войти'}
              </button>
            </>
          ) : (
            <SmsVerify
              key={phone}
              phone={phone}
              purpose="login"
              onVerified={(token) => void loginBySms(token)}
            />
          )}

          {error && <div className="notice notice--error"><Icon name="alert" size={17} /><span>{error}</span></div>}

          <div className="auth-divider"><span>или</span></div>

          <div className="auth-register">
            <span>Ещё нет аккаунта?</span>
            <Link to="/register" className="btn btn--outline btn--block">Зарегистрироваться</Link>
          </div>

          <p className="auth-legal">
            Продолжая, вы принимаете <Link to="/legal/offer">правила оформления заказов</Link> и{' '}
            <Link to="/legal/privacy">политику обработки персональных данных</Link>.
          </p>

          {import.meta.env.DEV && (
            <div className="auth-demo">
              <strong>Демо-доступ (только в режиме разработки)</strong>
              <span>Администратор: +375 29 111-22-33 / ChangeMe123!</span>
              <span>Продавец: +375 29 111-22-44 / Seller123!</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
