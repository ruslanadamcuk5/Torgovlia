import { useEffect, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Icon, type IconName } from './icons'
import { formatQty, statusLabel, statusTone, unitShort } from '../lib/format'

export function Spinner({ size = 22 }: { size?: number }) {
  return <span className="spinner" style={{ width: size, height: size }} aria-label="Загрузка" />
}

export function Loader({ label = 'Загружаем данные…' }: { label?: string }) {
  return (
    <div className="loader-block">
      <Spinner size={34} />
      <span>{label}</span>
    </div>
  )
}

export function EmptyState({
  icon = 'fish',
  title,
  text,
  action,
}: {
  icon?: IconName
  title: string
  text?: string
  action?: ReactNode
}) {
  return (
    <div className="empty-state">
      <span className="empty-state__icon"><Icon name={icon} size={28} /></span>
      <h3>{title}</h3>
      {text && <p>{text}</p>}
      {action}
    </div>
  )
}

export function Modal({
  title,
  subtitle,
  onClose,
  children,
  footer,
  size = 'md',
}: {
  title: string
  subtitle?: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  size?: 'sm' | 'md' | 'lg'
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [onClose])

  return createPortal(
    <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" className="modal__overlay" aria-label="Закрыть" onClick={onClose} />
      <div className={`modal__card modal__card--${size}`}>
        <header className="modal__head">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Закрыть">
            <Icon name="close" size={20} />
          </button>
        </header>
        <div className="modal__body">{children}</div>
        {footer && <footer className="modal__foot">{footer}</footer>}
      </div>
    </div>,
    document.body,
  )
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={`status status--${statusTone(status)}`}>{statusLabel(status)}</span>
}

export function QtyControl({
  value,
  onChange,
  unit,
  disabled = false,
  compact = false,
}: {
  value: number
  onChange: (value: number) => void
  unit: 'kg' | 'piece'
  disabled?: boolean
  compact?: boolean
}) {
  const step = unit === 'kg' ? 0.5 : 1
  return (
    <div className={`qty ${compact ? 'qty--compact' : ''}`}>
      <button
        type="button"
        aria-label="Уменьшить"
        disabled={disabled}
        onClick={() => onChange(Math.max(unit === 'kg' ? 0.1 : 1, Math.round((value - step) * 10) / 10))}
      >
        <Icon name="minus" size={16} />
      </button>
      <label className="qty__input">
        <input
          type="number"
          inputMode="decimal"
          min={unit === 'kg' ? 0.1 : 1}
          step={unit === 'kg' ? 0.1 : 1}
          value={value}
          disabled={disabled}
          onChange={(event) => {
            const parsed = Number(event.target.value)
            if (Number.isFinite(parsed)) onChange(parsed)
          }}
          aria-label="Количество"
        />
        <span>{unitShort(unit)}</span>
      </label>
      <button
        type="button"
        aria-label="Увеличить"
        disabled={disabled}
        onClick={() => onChange(Math.round((value + step) * 10) / 10)}
      >
        <Icon name="plus" size={16} />
      </button>
    </div>
  )
}

export function QuantityLabel({ value, unit }: { value: number; unit: 'kg' | 'piece' }) {
  return <>{formatQty(value)} {unitShort(unit)}</>
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <span className={`skeleton ${className}`} />
}

export function Tabs({ tabs, active, onChange }: { tabs: { id: string; label: string; count?: number }[]; active: string; onChange: (id: string) => void }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={active === tab.id}
          className={`tabs__item ${active === tab.id ? 'is-active' : ''}`}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
          {typeof tab.count === 'number' && <span className="tabs__count">{tab.count}</span>}
        </button>
      ))}
    </div>
  )
}

export function useDebounced<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay)
    return () => window.clearTimeout(timer)
  }, [value, delay])
  return debounced
}
