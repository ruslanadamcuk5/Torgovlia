export interface AccentOption {
  label: string
  value: string
}

export const ACCENT_OPTIONS: AccentOption[] = [
  { label: 'Бирюза', value: '#0b6b6b' },
  { label: 'Лес', value: '#1c5a43' },
  { label: 'Океан', value: '#1667a8' },
  { label: 'Ягода', value: '#8c2f5f' },
  { label: 'Терракота', value: '#c25a24' },
  { label: 'Зелень', value: '#2f8f4e' },
  { label: 'Графит', value: '#3a3a3a' },
  { label: 'Золото', value: '#8a6a2f' },
  { label: 'Слива', value: '#6b3fa0' },
  { label: 'Вино', value: '#b2423d' },
  { label: 'Какао', value: '#8a5a3b' },
  { label: 'Индиго', value: '#13355c' },
]

function parseHex(value: string): [number, number, number] | null {
  const raw = value.trim().replace(/^#/, '')
  if (!/^[0-9a-fA-F]{6}$/.test(raw)) return null
  return [
    Number.parseInt(raw.slice(0, 2), 16),
    Number.parseInt(raw.slice(2, 4), 16),
    Number.parseInt(raw.slice(4, 6), 16),
  ]
}

function toHex(rgb: [number, number, number]): string {
  return (
    '#' +
    rgb
      .map((channel) => Math.max(0, Math.min(255, Math.round(channel))).toString(16).padStart(2, '0'))
      .join('')
  )
}

function shade(value: string, factor: number): string {
  const rgb = parseHex(value)
  if (!rgb) return value
  return toHex(
    rgb.map((channel) =>
      factor >= 0 ? channel + (255 - channel) * factor : channel * (1 + factor),
    ) as [number, number, number],
  )
}

function mix(value: string, background: string, weight: number): string {
  const fg = parseHex(value)
  const bg = parseHex(background)
  if (!fg || !bg) return value
  return toHex(
    fg.map((channel, index) => channel * weight + bg[index] * (1 - weight)) as [number, number, number],
  )
}

/** Повторяет логику backend/app/platform/templates.py:apply_accent. */
export function applyAccent(tokens: Record<string, string>, accent?: string): Record<string, string> {
  if (!accent || !parseHex(accent)) return tokens
  return {
    ...tokens,
    teal: toHex(parseHex(accent)!),
    'teal-dark': shade(accent, -0.16),
    'teal-light': shade(accent, 0.14),
    'teal-soft': mix(accent, '#ffffff', 0.12),
    mint: mix(accent, '#ffffff', 0.26),
  }
}
