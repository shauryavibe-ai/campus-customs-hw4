import { createContext, useContext } from 'react'
import type { Bag, BagItem, Size } from './api'

export const MAX_PER_LINE = 10

export interface BagState {
  items: BagItem[]
  count: number
  /** Add `quantity` of a product+size, never more than `available` (or MAX_PER_LINE). Returns the new line quantity. */
  add: (productId: string, size: Size, quantity: number, available: number) => number
  setQuantity: (productId: string, size: Size, quantity: number) => void
  remove: (productId: string, size: Size) => void
  /** Replace the bag with what the server says (e.g. after a reservation was refused because stock changed). */
  applyServerBag: (bag: Bag) => void
  clear: () => void
}

export const BagContext = createContext<BagState | null>(null)

export function useBag(): BagState {
  const ctx = useContext(BagContext)
  if (!ctx) throw new Error('useBag must be used inside <BagProvider>')
  return ctx
}
