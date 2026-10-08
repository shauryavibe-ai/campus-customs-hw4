// Client for the FastAPI backend (Vite proxies /api and /media to http://127.0.0.1:8000).

// ---------- Chat API contract v1 ----------
// Mirrors backend/models.py (ProductCard, CardSize, ChatResponse). The chat widget renders cards
// ONLY from these fields. backend/test_contract.py fails if the two drift apart.
// Full description: outputs/api_contract.md

export type Size = 'XS' | 'S' | 'M' | 'L' | 'XL' | 'XXL'
export type StockStatus = 'in stock' | 'low stock' | 'sold out'

export interface CardSize {
  size: Size
  quantity: number
  status: StockStatus
}

export interface ProductCard {
  product_id: string
  name: string
  category: string
  garment_type: string
  price: number
  currency: 'USD'
  short_description: string | null
  colors: string[]
  image_url: string
  product_url: string
  sizes: CardSize[]
  sizes_in_stock: Size[]
  total_stock: number
  requested_size: Size | null
  requested_size_qty: number | null
}

export interface ChatResponse {
  contract_version: '1.0'
  reply: string
  products: ProductCard[]
  source: 'ai' | 'blocked' | 'fallback'
}

export interface ChatHistoryMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  page_product_id: string | null
  products: ProductCard[]
  created_at: string
}

export interface ChatHistory {
  contract_version: '1.0'
  messages: ChatHistoryMessage[]
}

// One earlier message sent back with each request (guests; logged-in history comes from the database).
export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
  product_ids?: string[] // assistant: the cards shown with that reply
  page_product_id?: string | null // user: the product page they were on when sending it
}

// ---------- Accounts ----------

export interface User {
  id: number
  first_name: string | null
  last_name: string | null
  name: string
  email: string
  created_at: string
}

export interface SignupInput {
  first_name: string
  last_name: string
  email: string
  password: string
}

export class ApiError extends Error {
  status: number
  body: unknown
  constructor(status: number, message: string, body: unknown = null) {
    super(message)
    this.status = status
    this.body = body
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, {
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch {
    throw new ApiError(0, "Can't reach the Campus Customs server. Is the backend running on port 8000?")
  }
  if (res.status === 204) return undefined as T
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = body?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : res.status >= 500
          ? "Can't reach the Campus Customs server. Is the backend running on port 8000?"
          : 'Please check the form and try again.'
    throw new ApiError(res.status, message, body)
  }
  return body as T
}

export const signup = (input: SignupInput) =>
  request<User>('/api/auth/signup', { method: 'POST', body: JSON.stringify(input) })

export const login = (email: string, password: string) =>
  request<User>('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })

export const logout = () => request<void>('/api/auth/logout', { method: 'POST' })

export async function currentUser(): Promise<User | null> {
  try {
    return await request<User>('/api/auth/me')
  } catch {
    return null
  }
}

// ---------- Chat ----------

export interface ChatStarters {
  greeting: string
  questions: string[]
}

export const getChatStarters = () => request<ChatStarters>('/api/chat/starters')

// Logged-in shoppers only: their saved conversation, oldest first.
export const getChatHistory = () => request<ChatHistory>('/api/chat/history')

export const sendChat = (message: string, history: ChatTurn[] = [], pageProductId: string | null = null) =>
  request<ChatResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ message, history, page_product_id: pageProductId }),
  })

// ---------- Bag and pickup reservations ----------
// Guests' bags live in the browser; logged-in shoppers' bags are saved on the server.

export interface BagItem {
  product_id: string
  size: Size
  quantity: number
}

export interface BagLine extends BagItem {
  name: string
  price: number
  image_url: string
  product_url: string
  available: number
  line_total: number
  status: 'ok' | 'reduced' | 'sold_out'
}

export interface Bag {
  items: BagLine[]
  count: number
  subtotal: number
}

export interface Reservation {
  code: string
  created_at: string
  name: string
  items: BagLine[]
  total: number
  pickup_address: string
  note: string
}

const bagBody = (items: BagItem[]) => JSON.stringify({ items })

export const checkBag = (items: BagItem[]) => request<Bag>('/api/bag/check', { method: 'POST', body: bagBody(items) })
export const getBag = () => request<Bag>('/api/bag')
export const putBag = (items: BagItem[]) => request<Bag>('/api/bag', { method: 'PUT', body: bagBody(items) })
export const reserveBag = () => request<Reservation>('/api/bag/reserve', { method: 'POST' })
