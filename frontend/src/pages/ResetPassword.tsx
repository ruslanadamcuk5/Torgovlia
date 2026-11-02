import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '../lib/api'
import { useToast } from '../store/ToastContext'
import { SmsVerify } from '../components/SmsVerify'
import { Spinner } from '../components/ui'
import { Icon } from '../components/icons'
import { normalizePhoneInput, phonePretty, samePhone } from '../lib/format'

export default function ResetPassword() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const [phone, setPhone] = useState('')
  const [token, setToken] = useState('')
  const [verifiedPhone, setVerifiedPhone] = useState('')
  const [password, setPassword] = useState('')
  const [repeat, setRepeat] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async () => {
    setError('')
    if (!token || !samePhone(verifiedPhone, phone)) return setError('Подтвердите номер телефона')
    if (password.length < 8) return setError('Пароль должен содержать минимум 8 символов')
    if (password !== repeat) return setError('Пароли не совпадают')
    setBusy(true)
    try {
      const result = await authApi.resetPassword(token, password)
      toast(result.message)
      navigate('/login', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось изменить пароль')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card auth-card--narrow">
        <Link to="/login" className="link-arrow"><Icon name="arrow-left" size={16} /> Ко входу</Link>
        <div className="auth-card__head">
          <h2>Восстановление пароля</h2>
          <p>Подтвердите номер телефона — и задайте новый пароль.</p>
        </div>

        <label className="field">
          <span className="field__label">Мобильный телефон</span>
          <input
            className="input"
            value={phone}
            onChange={(event) => { setPhone(normalizePhoneInput(event.target.value)); setToken(''); setVerifiedPhone('') }}
            onBlur={() => setPhone((value) => phonePretty(value))}
            placeholder="+375 29 123-45-67"
            inputMode="tel"
          />
        </label>

        {token && samePhone(verifiedPhone, phone) ? (
          <div className="verified-account"><Icon name="check" size={18} /> Номер подтверждён</div>
        ) : (
          <SmsVerify
            key={phone}
            phone={phone}
            purpose="reset"
            onVerified={(value, verified) => { setToken(value); setVerifiedPhone(verified) }}
          />
        )}

        <label className="field">
          <span className="field__label">Новый пароль</span>
          <input className="input" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Минимум 8 символов" />
        </label>
        <label className="field">
          <span className="field__label">Повторите пароль</span>
          <input className="input" type="password" value={repeat} onChange={(event) => setRepeat(event.target.value)} />
        </label>

        {error && <div className="notice notice--error"><Icon name="alert" size={17} /><span>{error}</span></div>}

        <button type="button" className="btn btn--primary btn--lg btn--block" onClick={submit} disabled={busy}>
          {busy ? <Spinner size={18} /> : 'Сохранить новый пароль'}
        </button>

        <p className="auth-legal">Если номер не зарегистрирован, <Link to="/register">создайте аккаунт</Link>.</p>
      </div>
    </div>
  )
}
