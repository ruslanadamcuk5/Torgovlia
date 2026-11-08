import { ean13Bars, ean13Digits, isValidEan13 } from '../lib/barcode'

export function Barcode({
  code,
  height = 46,
  className = '',
}: {
  code?: string | null
  height?: number
  className?: string
}) {
  if (!code || !isValidEan13(code)) {
    return <span className={`barcode barcode--empty ${className}`.trim()}>Нет штрихкода</span>
  }

  const bars = ean13Bars(code)
  const [prefix, left, right] = ean13Digits(code)

  return (
    <span className={`barcode ${className}`.trim()}>
      <svg
        viewBox="0 0 95 88"
        preserveAspectRatio="none"
        style={{ height }}
        role="img"
        aria-label={`Штрихкод ${code}`}
      >
        {bars.map((bar, index) => (
          <rect key={index} x={bar.x} y={0} width={bar.width} height={88} />
        ))}
      </svg>
      <span className="barcode__digits">
        <span>{prefix}</span>
        <span>{left}</span>
        <span>{right}</span>
      </span>
    </span>
  )
}
