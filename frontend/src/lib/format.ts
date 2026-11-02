export function formatMoney(value: number): string {
  const formatted = new Intl.NumberFormat('ru-BY', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value || 0)
  return `${formatted} BYN`
}

export function formatQty(value: number): string {
  const rounded = Math.round((value || 0) * 1000) / 1000
  return new Intl.NumberFormat('ru-BY', { maximumFractionDigits: 2 }).format(rounded)
}

export function unitShort(unit: 'kg' | 'piece'): string {
  return unit === 'kg' ? 'кг' : 'шт.'
}

export function plural(count: number, one: string, few: string, many: string): string {
  const abs = Math.abs(count) % 100
  const last = abs % 10
  if (abs > 10 && abs < 20) return many
  if (last > 1 && last < 5) return few
  if (last === 1) return one
  return many
}

const MONTHS = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
]
const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
const WEEKDAYS_FULL = [
  'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье',
]

export function parseDate(value: string): Date {
  return new Date(`${value}T12:00:00`)
}

export function humanDate(value: string): string {
  if (!value) return ''
  const date = parseDate(value)
  return `${date.getDate()} ${MONTHS[date.getMonth()]}`
}

export function humanDateFull(value: string): string {
  if (!value) return ''
  const date = parseDate(value)
  return `${date.getDate()} ${MONTHS[date.getMonth()]} ${date.getFullYear()}`
}

export function weekdayShort(value: string): string {
  return WEEKDAYS[parseDate(value).getDay() === 0 ? 6 : parseDate(value).getDay() - 1]
}

export function weekdayFull(index: number): string {
  return WEEKDAYS_FULL[index] ?? ''
}

export function todayIso(): string {
  const now = new Date()
  const local = new Date(now.getTime() + 3 * 60 * 60 * 1000)
  return local.toISOString().slice(0, 10)
}

export function addDaysIso(iso: string, days: number): string {
  const date = parseDate(iso)
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

export function phonePretty(value: string): string {
  const digits = value.replace(/\D/g, '')
  if (digits.length === 12 && digits.startsWith('375')) {
    return `+375 (${digits.slice(3, 5)}) ${digits.slice(5, 8)}-${digits.slice(8, 10)}-${digits.slice(10, 12)}`
  }
  return value
}

export function normalizePhoneInput(value: string): string {
  return value.replace(/[^\d+()\-\s]/g, '').slice(0, 20)
}

export function samePhone(a: string, b: string): boolean {
  const digits = (value: string) => value.replace(/\D/g, '').slice(-9)
  return digits(a).length === 9 && digits(a) === digits(b)
}

export function timeLabel(time: string): string {
  return time
}

export function statusLabel(status: string): string {
  const map: Record<string, string> = {
    new: 'Новая',
    confirmed: 'Подтверждена',
    ready: 'Готова к выдаче',
    completed: 'Выдана',
    cancelled: 'Отменена',
    rejected: 'Отклонена',
  }
  return map[status] ?? status
}

export function statusTone(status: string): string {
  const map: Record<string, string> = {
    new: 'warn',
    confirmed: 'info',
    ready: 'success',
    completed: 'muted',
    cancelled: 'danger',
    rejected: 'danger',
  }
  return map[status] ?? 'muted'
}

export function socialLabel(url: string): string {
  try {
    const host = new URL(url).hostname.replace('www.', '')
    return host
  } catch {
    return url
  }
}

export function socialHandle(url: string): string {
  try {
    const parsed = new URL(url)
    return parsed.pathname.replace(/^\/+|\/+$/g, '') || parsed.hostname
  } catch {
    return url
  }
}

export function isVideo(url: string): boolean {
  return /\.(mp4|webm|mov)$/i.test(url)
}

export function readingMinutes(text: string): number {
  return Math.max(3, Math.round(text.split(/\s+/).length / 150))
}
