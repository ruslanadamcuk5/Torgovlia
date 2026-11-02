import { useEffect, useRef, useState } from 'react'
import { authApi } from '../lib/api'
import { useToast } from '../store/ToastContext'
import { Icon } from './icons'
import { Spinner } from './ui'

type Purpose = 'register' | 'login' | 'order' | 'reset'

interface Props {
  phone: string
  purpose: Purpose
  onVerified: (phoneToken: string, phone: string) => void
  onReset?: () => void
}

export function SmsVerify({ phone, purpose, onVerified, onReset }: Props) {
  const { toast } = useToast()
  const [step, setStep] = useState<'idle' | 'sent' | 'verified'>('idle')
  const [verificationId, setVerificationId] = useState('')
  const [debugCode, setDebugCode] = useState<string | null>(null)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [seconds, setSeconds] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setStep('idle')
    setCode('')
    setError('')
    setDebugCode(null)
    setVerificationId('')
  }, [phone])

  useEffect(() => {
    if (seconds <= 0) return
    const timer = window.setTimeout(() => setSeconds((value) => value - 1), 1000)
    return () => window.clearTimeout(timer)
  }, [seconds])

  const request = async () => {
    if (phone.replace(/\D/g, '').length < 9) {
      setError('Введите номер полностью')
      return
    }
    setBusy(true)
    setError('')
    try {
      const data = await authApi.requestCode(phone, purpose)
      setVerificationId(data.verification_id)
      setDebugCode(data.debug_code ?? null)
      setStep('sent')
      setSeconds(60)
      window.setTimeout(() => inputRef.current?.focus(), 120)
      toast(data.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось отправить код')
    } finally {
      setBusy(false)
    }
  }

  const confirm = async () => {
    if (code.replace(/\D/g, '').length !== 6) {
      setError('Введите 6 цифр из SMS')
      return
    }
    setBusy(true)
    setError('')
    try {
      const data = await authApi.confirmCode(verificationId, code)
      setStep('verified')
      onVerified(data.phone_token, data.phone)
      toast('Номер телефона подтверждён', 'success')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Неверный код')
    } finally {
      setBusy(false)
    }
  }

  const reset = () => {
    setStep('idle')
    setCode('')
    setDebugCode(null)
    setError('')
    setVerificationId('')
    onReset?.()
  }

  if (step === 'verified') {
    return (
      <div className="sms sms--done">
        <span className="sms__badge"><Icon name="check" size={18} /> Номер подтверждён</span>
        <button type="button" className="link-btn" onClick={reset}>Изменить номер</button>
      </div>
    )
  }

  return (
    <div className="sms">
      {step === 'idle' ? (
        <button type="button" className="btn btn--outline" onClick={request} disabled={busy}>
          {busy ? <Spinner size={18} /> : <Icon name="phone" size={18} />}
          Получить код по SMS
        </button>
      ) : (
        <>
          <div className="sms__row">
            <input
              ref={inputRef}
              className="input sms__code"
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="— — — — — —"
              maxLength={6}
              value={code}
              onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void confirm()
              }}
              aria-label="Код из SMS"
            />
            <button type="button" className="btn btn--primary" onClick={confirm} disabled={busy}>
              {busy ? <Spinner size={18} /> : 'Подтвердить'}
            </button>
          </div>
          <div className="sms__meta">
            <span>Код отправлен на {phone}</span>
            {seconds > 0 ? (
              <span>Повторно через {seconds} с</span>
            ) : (
              <button type="button" className="link-btn" onClick={request} disabled={busy}>
                Отправить ещё раз
              </button>
            )}
          </div>
          {debugCode && (
            <div className="sms__debug">
              Тестовый режим (SMS не отправляется): код <strong>{debugCode}</strong>
            </div>
          )}
        </>
      )}
      {error && <div className="field__error">{error}</div>}
    </div>
  )
}
