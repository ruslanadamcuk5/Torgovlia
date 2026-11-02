import { NavLink, Link } from 'react-router-dom'
import type { Socials } from '../lib/types'
import { socialHandle } from '../lib/format'
import { Icon, type IconName } from './icons'

const ITEMS: { key: keyof Socials; label: string; icon: IconName; className: string }[] = [
  { key: 'tiktok', label: 'TikTok', icon: 'tiktok', className: 'social--tiktok' },
  { key: 'instagram', label: 'Instagram', icon: 'instagram', className: 'social--instagram' },
  { key: 'youtube', label: 'YouTube', icon: 'youtube', className: 'social--youtube' },
  { key: 'telegram', label: 'Telegram', icon: 'telegram', className: 'social--telegram' },
  { key: 'viber', label: 'Viber', icon: 'viber', className: 'social--viber' },
]

export function SocialLinks({ socials, variant = 'hero' }: { socials: Socials; variant?: 'hero' | 'footer' }) {
  const visible = ITEMS.filter((item) => Boolean(socials[item.key]))
  if (!visible.length) return null

  return (
    <div className={`socials socials--${variant}`}>
      {visible.map((item) => (
        <a
          key={item.key}
          href={socials[item.key]}
          target="_blank"
          rel="noopener noreferrer"
          className={`social-link ${item.className}`}
          aria-label={`${item.label} — открыть в новой вкладке`}
        >
          <span className="social-link__icon"><Icon name={item.icon} size={variant === 'hero' ? 26 : 20} /></span>
          <span className="social-link__text">
            <strong>{item.label}</strong>
            <span>{socialHandle(socials[item.key])}</span>
          </span>
          <Icon name="external" size={15} className="social-link__arrow" />
        </a>
      ))}
    </div>
  )
}
