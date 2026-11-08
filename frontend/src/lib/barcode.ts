/** Кодирование EAN-13 в полосы для SVG и печати. */

const L = [
  '0001101', '0011001', '0010011', '0111101', '0100011',
  '0110001', '0101111', '0111011', '0110111', '0001011',
]

const G = [
  '0100111', '0110011', '0011011', '0100001', '0011101',
  '0111001', '0000101', '0010001', '0001001', '0010111',
]

const R = [
  '1110010', '1100110', '1101100', '1000010', '1011100',
  '1001110', '1010000', '1000100', '1001000', '1110100',
]

const PARITY = [
  'LLLLLL', 'LLGLGG', 'LLGGLG', 'LLGGGL', 'LGLLGG',
  'LGGLLG', 'LGGGLL', 'LGLGLG', 'LGLGGL', 'LGGLGL',
]

export function ean13CheckDigit(base12: string): string {
  if (base12.length !== 12 || !/^\d{12}$/.test(base12)) return ''
  let total = 0
  for (let index = 0; index < 12; index += 1) {
    total += Number(base12[index]) * (index % 2 === 0 ? 1 : 3)
  }
  return String((10 - (total % 10)) % 10)
}

export function isValidEan13(code?: string | null): boolean {
  const value = (code ?? '').trim()
  return /^\d{13}$/.test(value) && ean13CheckDigit(value.slice(0, 12)) === value[12]
}

export interface BarcodeBar {
  x: number
  width: number
}

export function ean13Bars(code?: string | null): BarcodeBar[] {
  const value = (code ?? '').trim()
  if (!isValidEan13(value)) return []

  let modules = '101'
  const parity = PARITY[Number(value[0])]
  for (let index = 0; index < 6; index += 1) {
    const digit = Number(value[index + 1])
    modules += parity[index] === 'L' ? L[digit] : G[digit]
  }
  modules += '01010'
  for (let index = 0; index < 6; index += 1) {
    modules += R[Number(value[index + 7])]
  }
  modules += '101'

  const bars: BarcodeBar[] = []
  let start = -1
  for (let index = 0; index <= modules.length; index += 1) {
    const isBar = index < modules.length && modules[index] === '1'
    if (isBar && start < 0) start = index
    if (!isBar && start >= 0) {
      bars.push({ x: start, width: index - start })
      start = -1
    }
  }
  return bars
}

export function ean13Svg(code: string, height = 34): string {
  const bars = ean13Bars(code)
  if (!bars.length) return ''
  const rects = bars
    .map((bar) => `<rect x="${bar.x}" y="0" width="${bar.width}" height="88" />`)
    .join('')
  return `<svg class="barcode-svg" viewBox="0 0 95 88" preserveAspectRatio="none" style="width:100%;height:${height}px" role="img" aria-label="Штрихкод ${code}">${rects}</svg>`
}

export function ean13Digits(code: string): [string, string, string] {
  return [code.slice(0, 1), code.slice(1, 7), code.slice(7, 13)]
}
