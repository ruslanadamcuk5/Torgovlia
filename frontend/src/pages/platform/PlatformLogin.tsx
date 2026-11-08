import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { platformAuthApi, getPlatformToken, setPlatformToken } from '../../lib/platformApi'
import { track } from '../../lib/track'
import { normalizePhoneInput } from '../../lib/format'

export default function PlatformLogin() {
  const navigate = useNavigate()
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (getPlatformToken()) return <Navigate to="/platform" replace />

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const data = await platformAuthApi.login(normalizePhoneInput(phone), password, totpCode)
      setPlatformToken(data.access_token)
      track('platform_login')
      navigate('/platform', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось войти')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="platform-login">
      <form className="platform-login__card" onSubmit={submit}>
        <div className="platform-logo">T</div>
        <h1>Панель платформы</h1>
        <p>Управление магазинами, доменами, сервисами и тарифами.</p>

        <label className="field">
          <span className="field__label">Телефон</span>
          <input
            className="input"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            placeholder="+375 29 000-00-00"
            autoComplete="username"
          />
        </label>
        <label className="field">
          <span className="field__label">Пароль</span>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
          />
        </label>

        <label className="field">
          <span className="field__label">Код 2FA</span>
          <input
            className="input"
            value={totpCode}
            onChange={(event) => setTotpCode(event.target.value)}
            placeholder="6 цифр, если включена"
            inputMode="numeric"
            autoComplete="one-time-code"
          />
        </label>

        {error && <div className="form-error">{error}</div>}

        <button type="submit" className="btn btn--primary btn--block btn--lg" disabled={busy}>
          {busy ? 'Проверяем…' : 'Войти в платформу'}
        </button>
        <small>Доступ только для сотрудников платформы.</small>
      </form>
    </div>
  )
}
