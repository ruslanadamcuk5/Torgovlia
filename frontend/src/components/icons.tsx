import type { ReactNode, SVGProps } from 'react'

export type IconName =
  | 'fish' | 'cart' | 'user' | 'phone' | 'pin' | 'clock' | 'mail' | 'shield' | 'scissors'
  | 'check' | 'arrow-right' | 'arrow-left' | 'plus' | 'minus' | 'trash' | 'close' | 'menu'
  | 'search' | 'calendar' | 'star' | 'percent' | 'qr' | 'download' | 'print' | 'edit'
  | 'eye' | 'eye-off' | 'upload' | 'camera' | 'logout' | 'dashboard' | 'box' | 'users'
  | 'settings' | 'image' | 'tag' | 'chart' | 'list' | 'alert' | 'info' | 'sparkles'
  | 'chevron-down' | 'chevron-right' | 'external' | 'instagram' | 'tiktok' | 'youtube'
  | 'telegram' | 'viber' | 'map' | 'heart' | 'scale' | 'book' | 'android' | 'smartphone'
  | 'clock-fast' | 'wallet' | 'refresh' | 'lock' | 'send' | 'filter' | 'bell'

const STROKE: Partial<Record<IconName, ReactNode>> = {
  fish: (
    <>
      <path d="M3 12c2.5-4 6.2-6 10-6 3.9 0 6.9 2 8 6-1.1 4-4.1 6-8 6-3.8 0-7.5-2-10-6Z" />
      <path d="M3 12 1 8.5v7L3 12Z" />
      <circle cx="16.5" cy="10.5" r=".9" fill="currentColor" stroke="none" />
    </>
  ),
  cart: (
    <>
      <circle cx="9" cy="20" r="1.4" />
      <circle cx="18" cy="20" r="1.4" />
      <path d="M2 3h2.2l2.4 11.2a2 2 0 0 0 2 1.6h8.6a2 2 0 0 0 2-1.6L21 7H5" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c.7-4 3.8-6 8-6s7.3 2 8 6" />
    </>
  ),
  phone: <path d="M6.6 3h2.2l1.6 4-2 1.5a13 13 0 0 0 5.6 5.6l1.5-2 4 1.6v2.2A2.6 2.6 0 0 1 16.9 21C10 20.2 3.8 14 3 7.1A2.6 2.6 0 0 1 6.6 3Z" />,
  pin: (
    <>
      <path d="M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11Z" />
      <circle cx="12" cy="10" r="2.6" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5.4l3.4 2" />
    </>
  ),
  'clock-fast': (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2M4 5 2 7M20 5l2 2" />
    </>
  ),
  mail: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2.5" />
      <path d="m4 7 8 6 8-6" />
    </>
  ),
  shield: (
    <>
      <path d="M12 3 5 6v5c0 4.6 3 8.1 7 10 4-1.9 7-5.4 7-10V6l-7-3Z" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  scissors: (
    <>
      <circle cx="6" cy="6" r="2.5" />
      <circle cx="6" cy="18" r="2.5" />
      <path d="M8 7.5 20 19M8 16.5 20 5" />
    </>
  ),
  check: <path d="m4 12.5 5 5L20 6.5" />,
  'arrow-right': <path d="M4 12h16m-6-6 6 6-6 6" />,
  'arrow-left': <path d="M20 12H4m6 6-6-6 6-6" />,
  plus: <path d="M12 5v14M5 12h14" />,
  minus: <path d="M5 12h14" />,
  trash: (
    <>
      <path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14" />
      <path d="M10 11v6M14 11v6" />
    </>
  ),
  close: <path d="M6 6l12 12M18 6 6 18" />,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-4-4" />
    </>
  ),
  calendar: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="3" />
      <path d="M8 3v4M16 3v4M3 10h18" />
    </>
  ),
  star: <path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1-4.4-4.3 6.1-.9L12 3Z" />,
  percent: (
    <>
      <path d="M19 5 5 19" />
      <circle cx="7" cy="7" r="2.5" />
      <circle cx="17" cy="17" r="2.5" />
    </>
  ),
  qr: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <path d="M14 14h3v3h-3zM20 14v3M14 20h3M20 20h1" />
    </>
  ),
  download: <path d="M12 3v12m0 0 4.5-4.5M12 15l-4.5-4.5M4 20h16" />,
  print: (
    <>
      <path d="M7 8V3h10v5M7 17H4V9h16v8h-3" />
      <rect x="7" y="14" width="10" height="7" rx="1.5" />
      <circle cx="17" cy="11.5" r=".8" fill="currentColor" stroke="none" />
    </>
  ),
  edit: <path d="M4 20h4L20 8l-4-4L4 16v4Zm9-13 4 4" />,
  eye: (
    <>
      <path d="M2 12s3.5-6.5 10-6.5S22 12 22 12s-3.5 6.5-10 6.5S2 12 2 12Z" />
      <circle cx="12" cy="12" r="2.8" />
    </>
  ),
  'eye-off': (
    <>
      <path d="M3 3l18 18M10.6 6.1A11 11 0 0 1 12 6c6.5 0 10 6 10 6a17 17 0 0 1-3.2 3.9M6.3 7.4A16 16 0 0 0 2 12s3.5 6 10 6a11 11 0 0 0 4.2-.8" />
    </>
  ),
  upload: <path d="M12 21V9m0 0 4.5 4.5M12 9 7.5 13.5M4 4h16" />,
  camera: (
    <>
      <path d="M4 8h3l1.5-2h7L17 8h3v11H4V8Z" />
      <circle cx="12" cy="13" r="3.4" />
    </>
  ),
  logout: <path d="M10 4H4v16h6M14 8l4 4-4 4m-5-4h9" />,
  dashboard: (
    <>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
    </>
  ),
  box: (
    <>
      <path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z" />
      <path d="m4 7.5 8 4.5 8-4.5M12 12v9" />
    </>
  ),
  users: (
    <>
      <circle cx="9" cy="8" r="3.4" />
      <path d="M2.5 20c.5-3.4 3-5.2 6.5-5.2s6 1.8 6.5 5.2" />
      <path d="M16 5.2a3.4 3.4 0 0 1 0 6.6M17.5 15c2.4.4 3.8 2.1 4 5" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
    </>
  ),
  image: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2.5" />
      <circle cx="8.5" cy="9.5" r="1.6" />
      <path d="m4 18 5-5 4 4 3-2.5 4 3.5" />
    </>
  ),
  tag: (
    <>
      <path d="M3 12V4h8l10 10-7 7L3 12Z" />
      <circle cx="7.5" cy="7.5" r="1.3" />
    </>
  ),
  chart: <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />,
  list: <path d="M9 6h12M9 12h12M9 18h12M4 6h.1M4 12h.1M4 18h.1" />,
  alert: (
    <>
      <path d="M12 3 2 21h20L12 3Z" />
      <path d="M12 9v5M12 17.5v.5" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v6M12 7.5v.5" />
    </>
  ),
  sparkles: <path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3ZM19 16l.9 2.1L22 19l-2.1.9L19 22l-.9-2.1L16 19l2.1-.9L19 16Z" />,
  'chevron-down': <path d="m6 9 6 6 6-6" />,
  'chevron-right': <path d="m9 6 6 6-6 6" />,
  external: <path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />,
  instagram: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="5.2" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="17.4" cy="6.6" r="1" fill="currentColor" stroke="none" />
    </>
  ),
  tiktok: (
    <path
      d="M15.2 3.2c.4 2.6 2 4.2 4.6 4.4v3.1c-1.8 0-3.4-.6-4.6-1.6v6.1a5.9 5.9 0 1 1-5.9-5.9c.4 0 .8 0 1.2.1v3.3a2.6 2.6 0 1 0 1.8 2.5V3.2h2.9Z"
      fill="currentColor"
      stroke="none"
    />
  ),
  youtube: (
    <>
      <rect x="2.2" y="5.2" width="19.6" height="13.6" rx="4.2" />
      <path d="m10.3 9.2 5.2 2.8-5.2 2.8V9.2Z" fill="currentColor" stroke="none" />
    </>
  ),
  telegram: <path d="M21 4 3.4 10.8l5.2 1.7L10.5 20l3.4-4.7 5 3.6L21 4Z" />,
  viber: (
    <>
      <path d="M7 3h1.8L10.5 7 8.8 8.5a12 12 0 0 0 4.7 4.7L15 11.5l4 1.7V15a3 3 0 0 1-3 3c-6-.7-11.3-6-12-12a3 3 0 0 1 3-3Z" />
      <path d="M15 4.5c2.5.6 4 2.1 4.6 4.6" />
    </>
  ),
  map: (
    <>
      <path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Z" />
      <path d="M9 3v15M15 6v15" />
    </>
  ),
  heart: <path d="M12 20s-7-4.4-7-9a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 4.6-7 9-7 9Z" />,
  scale: (
    <>
      <path d="M12 3v18M6 21h12M4 7h16" />
      <path d="m7 7-3 6h6L7 7ZM17 7l-3 6h6l-3-6Z" />
    </>
  ),
  book: (
    <>
      <path d="M4 5a2 2 0 0 1 2-2h14v16H6a2 2 0 0 0-2 2V5Z" />
      <path d="M4 19V5M8 7h8M8 11h6" />
    </>
  ),
  android: (
    <>
      <path d="M5 11a7 7 0 0 1 14 0v7H5v-7Z" />
      <path d="M8 5 6.5 2.5M16 5l1.5-2.5M9 9h.1M15 9h.1" />
    </>
  ),
  smartphone: (
    <>
      <rect x="6" y="2.5" width="12" height="19" rx="2.5" />
      <path d="M10 5h4M11 18.5h2" />
    </>
  ),
  wallet: (
    <>
      <rect x="3" y="6" width="18" height="14" rx="3" />
      <path d="M3 9h18M16 14h2" />
    </>
  ),
  refresh: <path d="M20 11a8 8 0 1 0-2.3 6.3M20 4v7h-7" />,
  lock: (
    <>
      <rect x="4" y="10" width="16" height="11" rx="2.5" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3" />
    </>
  ),
  send: <path d="m22 2-7 20-4-9-9-4 20-7Z" />,
  filter: <path d="M3 5h18l-7 8v6l-4 2v-8L3 5Z" />,
  bell: (
    <>
      <path d="M18 9a6 6 0 1 0-12 0c0 5-2 6-2 6h16s-2-1-2-6Z" />
      <path d="M10 20a2.2 2.2 0 0 0 4 0" />
    </>
  ),
}

interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'name'> {
  name: IconName
  size?: number
}

export function Icon({ name, size = 20, className, ...rest }: IconProps) {
  const content = STROKE[name]
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
      {...rest}
    >
      {content}
    </svg>
  )
}
