import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError, checkBag, reserveBag, type Bag as ServerBag, type Reservation } from '../api'
import { formatPrice, getProduct } from '../data/catalog'
import { MAX_PER_LINE, useBag } from '../useBag'
import { useAuth } from '../useAuth'

export default function Bag() {
  const { user } = useAuth()
  const bag = useBag()
  const navigate = useNavigate()
  const [reserving, setReserving] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const [reservation, setReservation] = useState<Reservation | null>(null)
  // Live stock per line from the server (inventory table); the site's catalogue copy is the fallback.
  const [live, setLive] = useState<Record<string, number>>({})

  useEffect(() => {
    if (bag.items.length === 0) return
    let cancelled = false
    checkBag(bag.items)
      .then((checked) => {
        if (!cancelled) setLive(Object.fromEntries(checked.items.map((l) => [`${l.product_id}:${l.size}`, l.available])))
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [bag.items])

  if (reservation) return <Confirmation reservation={reservation} />

  const lines = bag.items
    .map((item) => {
      const product = getProduct(item.product_id)
      if (!product) return null
      const key = `${item.product_id}:${item.size}`
      const available = key in live ? live[key] : (product.sizes.find((s) => s.size === item.size)?.qty ?? 0)
      return { item, product, available }
    })
    .filter((l) => l !== null)

  const payable = lines.filter((l) => l.available > 0)
  const subtotal = payable.reduce((sum, l) => sum + l.product.price * Math.min(l.item.quantity, l.available), 0)
  const blocked = lines.some((l) => l.available === 0 || l.item.quantity > l.available)

  const reserve = async () => {
    setProblem(null)
    setReserving(true)
    try {
      const done = await reserveBag()
      bag.applyServerBag({ items: [], count: 0, subtotal: 0 })
      setReservation(done)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        const updated = (err.body as { bag?: ServerBag } | null)?.bag
        if (updated) {
          setLive(Object.fromEntries(updated.items.map((l) => [`${l.product_id}:${l.size}`, l.available])))
          bag.applyServerBag(updated)
        }
      }
      setProblem(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setReserving(false)
    }
  }

  return (
    <div className="bag-page">
      <div className="page-head">
        <span className="eyebrow">Your Bag</span>
        <h1>{lines.length ? 'Ready for pickup?' : 'Your bag is empty'}</h1>
        <p className="muted">
          No online checkout yet: reserve your picks and pay when you collect them at 57 Broadway.
        </p>
      </div>

      {lines.length === 0 ? (
        <Link to="/products" className="btn btn-primary">
          Shop the catalog
        </Link>
      ) : (
        <div className="bag-layout">
          <ul className="bag-lines">
            {lines.map(({ item, product, available }) => {
              const max = Math.min(MAX_PER_LINE, available)
              const soldOut = available === 0
              const tooMany = !soldOut && item.quantity > available
              return (
                <li key={`${item.product_id}-${item.size}`} className={`bag-line${soldOut ? ' bag-line-out' : ''}`}>
                  <Link to={`/products/${product.id}?size=${item.size}`} className="bag-line-image">
                    <img src={product.image} alt={product.name} />
                  </Link>
                  <div className="bag-line-info">
                    <Link to={`/products/${product.id}?size=${item.size}`} className="bag-line-name">
                      {product.name}
                    </Link>
                    <span className="muted small">
                      Size {item.size} · {formatPrice(product.price)} each
                    </span>
                    {soldOut && (
                      <span className="bag-warning">
                        Sold out in {item.size}.{' '}
                        <Link to={`/products/${product.id}`}>Choose another size</Link>
                      </span>
                    )}
                    {tooMany && (
                      <span className="bag-warning">
                        Only {available} left in {item.size}.{' '}
                        <button type="button" className="link-button" onClick={() => bag.setQuantity(item.product_id, item.size, available)}>
                          Update to {available}
                        </button>
                      </span>
                    )}
                    <div className="bag-line-controls">
                      <div className="qty" aria-label={`Quantity of ${product.name}`}>
                        <button
                          type="button"
                          onClick={() => bag.setQuantity(item.product_id, item.size, item.quantity - 1)}
                          disabled={item.quantity <= 1 || soldOut}
                          aria-label="Decrease quantity"
                        >
                          −
                        </button>
                        <span>{item.quantity}</span>
                        <button
                          type="button"
                          onClick={() => bag.setQuantity(item.product_id, item.size, item.quantity + 1)}
                          disabled={soldOut || item.quantity >= max}
                          aria-label="Increase quantity"
                        >
                          +
                        </button>
                      </div>
                      <button type="button" className="link-button" onClick={() => bag.remove(item.product_id, item.size)}>
                        Remove
                      </button>
                    </div>
                  </div>
                  <span className="bag-line-total">
                    {soldOut ? '—' : formatPrice(product.price * Math.min(item.quantity, available))}
                  </span>
                </li>
              )
            })}
          </ul>

          <aside className="bag-summary">
            <div className="bag-summary-row">
              <span>Items</span>
              <span>{payable.reduce((n, l) => n + Math.min(l.item.quantity, l.available), 0)}</span>
            </div>
            <div className="bag-summary-row bag-summary-total">
              <span>Subtotal</span>
              <span>{formatPrice(subtotal)}</span>
            </div>
            <p className="muted small">Pay in store at pickup. Stock is checked again when you reserve.</p>

            {problem && (
              <p className="form-error" role="alert">
                {problem}
              </p>
            )}

            {user ? (
              <button
                type="button"
                className="btn btn-primary btn-block"
                onClick={reserve}
                disabled={reserving || blocked || payable.length === 0}
              >
                {reserving ? 'Reserving…' : 'Reserve for pickup at 57 Broadway'}
              </button>
            ) : (
              <>
                <button
                  type="button"
                  className="btn btn-primary btn-block"
                  onClick={() => navigate('/login', { state: { from: '/bag' } })}
                >
                  Log in to reserve
                </button>
                <p className="muted small">
                  New here? <Link to="/create-account">Create an account</Link>. Your bag comes with you.
                </p>
              </>
            )}
            {blocked && <p className="muted small">Fix the items marked above to reserve.</p>}
          </aside>
        </div>
      )}
    </div>
  )
}

function Confirmation({ reservation }: { reservation: Reservation }) {
  return (
    <div className="auth">
      <div className="auth-card auth-card-wide">
        <span className="eyebrow">Reserved</span>
        <h1>See you at 57 Broadway!</h1>
        <p className="muted">{reservation.note}</p>
        <div className="reservation-code" aria-label="Reservation code">
          {reservation.code}
        </div>
        <ul className="reservation-lines">
          {reservation.items.map((line) => (
            <li key={`${line.product_id}-${line.size}`}>
              <span>
                {line.quantity} × {line.name} ({line.size})
              </span>
              <span>{formatPrice(line.line_total)}</span>
            </li>
          ))}
          <li className="reservation-total">
            <span>Total due at pickup</span>
            <span>{formatPrice(reservation.total)}</span>
          </li>
        </ul>
        <p className="muted small">
          {reservation.name} · {reservation.pickup_address}
        </p>
        <div className="auth-actions">
          <Link to="/products" className="btn btn-primary">
            Keep shopping
          </Link>
        </div>
      </div>
    </div>
  )
}
