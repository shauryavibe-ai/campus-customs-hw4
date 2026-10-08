import { useEffect, useState, type ReactNode } from 'react'
import { getBag, putBag, type Bag, type BagItem, type Size } from './api'
import { BagContext, MAX_PER_LINE, type BagState } from './useBag'
import { useAuth } from './useAuth'

// Guests: the bag lives in this browser (localStorage). Logged in: it's saved to the account
// (backend/bag.py), and anything a guest added before logging in is merged into it once.

const STORAGE_KEY = 'cc_bag'

function readLocal(): BagItem[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]')
    return Array.isArray(parsed) ? parsed.filter((i) => i && i.product_id && i.size && i.quantity > 0) : []
  } catch {
    return []
  }
}

const toItems = (bag: Bag): BagItem[] => bag.items.map(({ product_id, size, quantity }) => ({ product_id, size, quantity }))
const same = (a: BagItem, productId: string, size: Size) => a.product_id === productId && a.size === size

function merge(base: BagItem[], extra: BagItem[]): BagItem[] {
  const out = base.map((i) => ({ ...i }))
  for (const item of extra) {
    const hit = out.find((i) => same(i, item.product_id, item.size))
    if (hit) hit.quantity = Math.min(MAX_PER_LINE, hit.quantity + item.quantity)
    else out.push({ ...item })
  }
  return out
}

// One account sync per login, shared by React's double-run of effects in development, so a
// guest bag is never merged into the account twice.
let inflight: { userId: number; promise: Promise<BagItem[]> } | null = null

function syncAccount(userId: number): Promise<BagItem[]> {
  if (inflight?.userId === userId) return inflight.promise
  const promise = getBag().then(async (saved) => {
    const local = readLocal()
    localStorage.removeItem(STORAGE_KEY)
    return local.length ? toItems(await putBag(merge(toItems(saved), local))) : toItems(saved)
  })
  inflight = { userId, promise }
  promise.catch(() => (inflight = null))
  return promise
}

export function BagProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const userId = user?.id
  const [guestItems, setGuestItems] = useState<BagItem[]>(readLocal)
  const [accountItems, setAccountItems] = useState<BagItem[]>([])

  useEffect(() => {
    if (userId === undefined) {
      inflight = null
      localStorage.setItem(STORAGE_KEY, JSON.stringify(guestItems))
    }
  }, [guestItems, userId])

  useEffect(() => {
    if (userId === undefined) return
    let cancelled = false
    syncAccount(userId)
      .then((items) => {
        if (cancelled) return
        setAccountItems(items)
        setGuestItems([])
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [userId])

  const items = userId === undefined ? guestItems : accountItems

  const commit = (next: BagItem[]) => {
    if (userId === undefined) {
      setGuestItems(next)
      return
    }
    setAccountItems(next) // show the change immediately, then take the server's checked version
    putBag(next)
      .then((bag) => setAccountItems(toItems(bag)))
      .catch(() => undefined)
  }

  const value: BagState = {
    items,
    count: items.reduce((n, i) => n + i.quantity, 0),
    add: (productId, size, quantity, available) => {
      const cap = Math.min(MAX_PER_LINE, available)
      const current = items.find((i) => same(i, productId, size))?.quantity ?? 0
      const next = Math.min(cap, current + quantity)
      if (next <= 0) return current
      commit(
        current
          ? items.map((i) => (same(i, productId, size) ? { ...i, quantity: next } : i))
          : [...items, { product_id: productId, size, quantity: next }],
      )
      return next
    },
    setQuantity: (productId, size, quantity) =>
      commit(items.map((i) => (same(i, productId, size) ? { ...i, quantity: Math.max(1, Math.min(MAX_PER_LINE, quantity)) } : i))),
    remove: (productId, size) => commit(items.filter((i) => !same(i, productId, size))),
    applyServerBag: (bag) => (userId === undefined ? setGuestItems(toItems(bag)) : setAccountItems(toItems(bag))),
    clear: () => commit([]),
  }

  return <BagContext.Provider value={value}>{children}</BagContext.Provider>
}
