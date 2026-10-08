import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useLocation } from 'react-router-dom'
import { getChatHistory, getChatStarters, sendChat, type ChatTurn, type ProductCard } from '../api'
import Bulldog from './Bulldog'
import ChatProductCard from './ChatProductCard'
import { getProduct } from '../data/catalog'
import { useAuth } from '../useAuth'

export interface ChatTopic {
  productName: string
  questions: string[]
}

interface Props {
  open: boolean
  setOpen: (open: boolean) => void
  topic: ChatTopic | null // set by "Ask about this item" on a product page
}

interface Message {
  id: number
  role: 'user' | 'bot'
  text: string
  products?: ProductCard[]
  error?: boolean
  fallback?: boolean
  saved?: boolean // loaded from the shopper's account (an earlier visit)
  pageProductId?: string | null // user messages: the product page they were on when sending it
}

// Used until /api/chat/starters loads (or if the backend is down).
const DEFAULT_GREETING = 'What do you need today? What products are you looking for?'
const DEFAULT_QUESTIONS = [
  'Do you have hoodies in my size?',
  "What's your cheapest crewneck?",
  'Show me gear for my residential college',
  'I need a gift for a Yale parent',
]
const MAX_HISTORY = 20

// Older saved replies (from a previous version of the assistant) contain Markdown bold markers.
const plainText = (text: string) => text.replace(/\*\*(.+?)\*\*/g, '$1')

function welcome(greeting: string, firstName?: string | null): Message {
  return {
    id: 0,
    role: 'bot',
    text: `Woof${firstName ? `, ${firstName}` : ''}! I'm Dan, the Campus Customs bulldog. ${greeting}`,
  }
}

// The conversation so far, in the shape the backend expects (error bubbles left out). Each reply
// carries the cards it showed and each message the page it was sent from, so the agent knows
// what "this" means. (For logged-in shoppers the server uses their saved history instead.)
function toHistory(messages: Message[]): ChatTurn[] {
  return messages
    .filter((m) => !m.error)
    .map(
      (m): ChatTurn =>
        m.role === 'user'
          ? { role: 'user', content: m.text, page_product_id: m.pageProductId ?? null }
          : { role: 'assistant', content: m.text, product_ids: (m.products ?? []).map((p) => p.product_id) },
    )
    .slice(-MAX_HISTORY)
}

// What the assistant will take "this" to mean. Mirrors the agent's rules in prompts.md:
// moved to a new product page -> that page; the last reply showed one product -> that one;
// otherwise the product page they're on.
function currentSubject(messages: Message[], pageProductId: string | null): string | null {
  const real = messages.filter((m) => !m.error)
  const lastUser = [...real].reverse().find((m) => m.role === 'user')
  const lastBot = real.length && real[real.length - 1].role === 'bot' ? real[real.length - 1] : null
  const pageName = pageProductId ? getProduct(pageProductId)?.name ?? null : null
  if (pageName && lastUser && lastUser.pageProductId !== pageProductId) return pageName
  if (lastBot?.products?.length === 1) return lastBot.products[0].name
  return pageName
}

export default function ChatWidget({ open, setOpen, topic }: Props) {
  const { user } = useAuth()
  const { pathname } = useLocation()
  const pageProductId = pathname.match(/^\/products\/([^/]+)$/)?.[1] ?? null
  const [messages, setMessages] = useState<Message[]>([])
  const [starters, setStarters] = useState({ greeting: DEFAULT_GREETING, questions: DEFAULT_QUESTIONS })
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const nextId = useRef(1)
  const listRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    getChatStarters()
      .then(setStarters)
      .catch(() => undefined)
  }, [])

  // Logged-in shoppers pick up their saved conversation. (Layout remounts this widget when the
  // logged-in user changes, so a different shopper never sees someone else's chat.)
  const userId = user?.id
  useEffect(() => {
    if (userId === undefined) return
    getChatHistory()
      .then((h) =>
        // Replace (not prepend) any saved messages, so loading twice never duplicates them.
        setMessages((current) => [
          ...h.messages.map((m) => ({
            id: nextId.current++,
            role: m.role === 'user' ? ('user' as const) : ('bot' as const),
            text: plainText(m.content),
            products: m.products,
            pageProductId: m.page_product_id,
            saved: true,
          })),
          ...current.filter((m) => !m.saved),
        ]),
      )
      .catch(() => undefined)
  }, [userId])

  // Keep the newest message in view: jump to the bottom when the panel opens (e.g. with saved
  // history), and scroll smoothly as new messages arrive.
  useEffect(() => {
    if (open) listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [open])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, sending])

  useEffect(() => {
    if (!open) return
    inputRef.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, setOpen])

  const send = async (text: string) => {
    const message = text.trim()
    if (!message || sending) return
    const history = toHistory(messages)
    setDraft('')
    setMessages((m) => [...m, { id: nextId.current++, role: 'user', text: message, pageProductId }])
    setSending(true)
    try {
      const res = await sendChat(message, history, pageProductId)
      setMessages((m) => [
        ...m,
        {
          id: nextId.current++,
          role: 'bot',
          text: res.reply,
          products: res.products,
          fallback: res.source === 'fallback',
        },
      ])
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          id: nextId.current++,
          role: 'bot',
          error: true,
          text: err instanceof Error ? err.message : "Something went wrong. Please try again.",
        },
      ])
    } finally {
      setSending(false)
    }
  }

  // The greeting is derived (not stored) so it picks up the shopper's name after login.
  const shown = [welcome(starters.greeting, user?.first_name), ...messages]
  const subject = currentSubject(messages, pageProductId)

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    void send(draft)
  }

  return (
    <div className="chat">
      {open && (
        <section className="chat-panel" role="dialog" aria-label="Campus Customs chat">
          <header className="chat-header">
            <div className="chat-header-id">
              <span className="chat-header-avatar">
                <Bulldog size={42} mood={sending ? 'thinking' : 'idle'} />
              </span>
              <div>
                <strong>Dan · Campus Customs</strong>
                <span>AI shop helper · checks live stock</span>
              </div>
            </div>
            <button type="button" className="chat-close" onClick={() => setOpen(false)} aria-label="Close chat">
              <span className="chat-close-label">Back to page</span>
              <span aria-hidden="true">×</span>
            </button>
          </header>

          {subject && (
            <div className="chat-subject" title="When you say “this” or “it”, the assistant will assume you mean this item. Name another item to switch.">
              Talking about: <strong>{subject}</strong>
            </div>
          )}

          <div className="chat-messages" ref={listRef} aria-live="polite">
            {shown.map((m, i) => (
              <div key={m.id} className={`chat-msg chat-${m.role}${m.error ? ' chat-error' : ''}`}>
                {m.saved && !shown[i - 1]?.saved && <span className="chat-divider">Saved from your earlier chats</span>}
                {m.role === 'bot' && (
                  <span className="chat-avatar" aria-hidden="true">
                    <Bulldog size={28} />
                  </span>
                )}
                <p>{m.text}</p>
                {m.fallback && <span className="chat-note">Quick answer: the AI assistant is offline right now.</span>}
                {m.products && m.products.length > 0 && (
                  <ul className="chat-products">
                    {m.products.map((card) => (
                      <li key={card.product_id}>
                        {/* Opening a product minimizes the chat so the product isn't covered */}
                        <ChatProductCard card={card} onNavigate={() => setOpen(false)} />
                      </li>
                    ))}
                  </ul>
                )}
                {m.saved && shown[i + 1] && !shown[i + 1].saved && <span className="chat-divider">New messages</span>}
              </div>
            ))}
            {sending && (
              <div className="chat-msg chat-bot chat-thinking" aria-label="Dan is looking that up">
                <span className="chat-avatar" aria-hidden="true">
                  <Bulldog size={28} mood="thinking" />
                </span>
                <div className="chat-typing">
                  <span />
                  <span />
                  <span />
                  <em>Dan is sniffing out the catalogue…</em>
                </div>
              </div>
            )}
          </div>

          {topic && (
            <div className="chat-topic">
              <span className="chat-topic-label">About {topic.productName}:</span>
              {topic.questions.map((q) => (
                <button key={q} type="button" onClick={() => void send(q)} disabled={sending}>
                  {q}
                </button>
              ))}
            </div>
          )}

          <div className="chat-starters">
            <select
              value=""
              onChange={(e) => void send(e.target.value)}
              disabled={sending}
              aria-label="Common questions"
            >
              <option value="" disabled>
                Common questions…
              </option>
              {starters.questions.map((q) => (
                <option key={q} value={q}>
                  {q}
                </option>
              ))}
            </select>
          </div>

          <form className="chat-input" onSubmit={onSubmit}>
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask about a style, size or college…"
              maxLength={500}
              aria-label="Chat message"
            />
            <button type="submit" disabled={!draft.trim() || sending} aria-label="Send message">
              ➤
            </button>
          </form>
        </section>
      )}

      <button
        type="button"
        className={`chat-toggle${open ? ' chat-toggle-open' : ''}`}
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-label={open ? 'Close chat' : 'Chat with Dan the bulldog'}
      >
        {open ? (
          '×'
        ) : (
          <>
            <span className="chat-toggle-dog">
              <Bulldog size={40} />
            </span>
            <span>{messages.length > 0 ? 'Continue chat' : 'Ask Dan'}</span>
          </>
        )}
      </button>
    </div>
  )
}
