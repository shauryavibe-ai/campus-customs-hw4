import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { ProductCard } from '../api'
import { useBag } from '../useBag'

// Renders one card from the chat API contract (backend/models.py ProductCard).
// Everything shown comes from the API response; nothing is looked up locally.

function stockLine(card: ProductCard): string {
  const { requested_size: size, requested_size_qty: qty } = card
  if (size && qty !== null) {
    if (qty === 0) return `Sold out in ${size}`
    const status = card.sizes.find((s) => s.size === size)?.status
    return status === 'low stock' ? `Only ${qty} left in ${size}` : `In stock in ${size}`
  }
  if (card.total_stock === 0) return 'Sold out'
  return card.sizes_in_stock.length === 6 ? 'All sizes in stock' : `${card.sizes_in_stock.length} of 6 sizes in stock`
}

const formatPrice = (price: number) => `$${price.toFixed(2)}`
const withSize = (url: string, size: string | null) => (size ? `${url}?size=${size}` : url)

interface Props {
  card: ProductCard
  onNavigate?: () => void // e.g. minimize the chat so the product page isn't covered
}

export default function ChatProductCard({ card, onNavigate }: Props) {
  const bag = useBag()
  const [added, setAdded] = useState(false)
  const size = card.requested_size
  const canAdd = size !== null && (card.requested_size_qty ?? 0) > 0

  const addToBag = () => {
    if (!size) return
    bag.add(card.product_id, size, 1, card.requested_size_qty ?? 0)
    setAdded(true)
  }

  return (
    <div className="chat-card">
      <Link to={withSize(card.product_url, size)} className="chat-card-main" onClick={onNavigate}>
        <img src={card.image_url} alt={card.name} loading="lazy" />
        <span className="chat-card-body">
          <span className="chat-card-category">{card.category}</span>
          <strong className="chat-card-name">{card.name}</strong>
          {card.short_description && <span className="chat-card-desc">{card.short_description}</span>}
          <span className="chat-card-meta">
            <span className="chat-card-price">{formatPrice(card.price)}</span>
            <span className={card.requested_size_qty === 0 ? 'chat-card-out' : ''}>{stockLine(card)}</span>
          </span>
        </span>
      </Link>
      <div className="chat-card-actions">
        <span className="chat-card-sizes" aria-label="Open in a size">
          {card.sizes.map((s) =>
            s.status === 'sold out' ? (
              <span key={s.size} className="size-dot sold_out" title={`${s.size}: sold out`}>
                {s.size}
              </span>
            ) : (
              <Link
                key={s.size}
                to={withSize(card.product_url, s.size)}
                onClick={onNavigate}
                className={`size-dot ${s.status.replace(' ', '_')}${s.size === size ? ' requested' : ''}`}
                title={`Open in ${s.size} (${s.status})`}
              >
                {s.size}
              </Link>
            ),
          )}
        </span>
        {canAdd &&
          (added ? (
            <Link to="/bag" className="chat-card-add added" onClick={onNavigate}>
              Added ✓ View bag
            </Link>
          ) : (
            <button type="button" className="chat-card-add" onClick={addToBag}>
              + Add {size} to bag
            </button>
          ))}
      </div>
    </div>
  )
}
