import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { CartLine, Product } from '../lib/types'

const STORAGE_KEY = 'rl_cart'

interface CartContextValue {
  lines: CartLine[]
  count: number
  subtotal: number
  add: (product: Product, quantity?: number) => void
  setQuantity: (productId: number, quantity: number) => void
  remove: (productId: number) => void
  clear: () => void
  has: (productId: number) => boolean
}

const CartContext = createContext<CartContextValue | null>(null)

function load(): CartLine[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((line) => line && typeof line.productId === 'number' && Number(line.quantity) > 0)
  } catch {
    return []
  }
}

function clampQuantity(unit: 'kg' | 'piece', value: number): number {
  if (!Number.isFinite(value)) return unit === 'kg' ? 0.5 : 1
  const max = unit === 'kg' ? 50 : 999
  const min = unit === 'kg' ? 0.1 : 1
  const rounded = unit === 'kg' ? Math.round(value * 10) / 10 : Math.round(value)
  return Math.min(max, Math.max(min, rounded))
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>(load)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(lines))
  }, [lines])

  const add = useCallback((product: Product, quantity = 1) => {
    setLines((current) => {
      const existing = current.find((line) => line.productId === product.id)
      if (existing) {
        return current.map((line) =>
          line.productId === product.id
            ? { ...line, quantity: clampQuantity(line.unit, line.quantity + quantity) }
            : line,
        )
      }
      return [
        ...current,
        {
          productId: product.id,
          slug: product.slug,
          title: product.title,
          image_url: product.image_url,
          unit: product.unit,
          price: product.final_price,
          quantity: clampQuantity(product.unit, quantity),
          is_available: product.is_available && product.can_order,
        },
      ]
    })
  }, [])

  const setQuantity = useCallback((productId: number, quantity: number) => {
    setLines((current) =>
      current
        .map((line) =>
          line.productId === productId ? { ...line, quantity: clampQuantity(line.unit, quantity) } : line,
        )
        .filter((line) => line.quantity > 0),
    )
  }, [])

  const remove = useCallback((productId: number) => {
    setLines((current) => current.filter((line) => line.productId !== productId))
  }, [])

  const clear = useCallback(() => setLines([]), [])

  const subtotal = useMemo(
    () => Math.round(lines.reduce((sum, line) => sum + line.price * line.quantity, 0) * 100) / 100,
    [lines],
  )

  const value = useMemo<CartContextValue>(
    () => ({
      lines,
      count: lines.length,
      subtotal,
      add,
      setQuantity,
      remove,
      clear,
      has: (id: number) => lines.some((line) => line.productId === id),
    }),
    [lines, subtotal, add, setQuantity, remove, clear],
  )

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}

export function useCart(): CartContextValue {
  const context = useContext(CartContext)
  if (!context) throw new Error('useCart must be used within CartProvider')
  return context
}
