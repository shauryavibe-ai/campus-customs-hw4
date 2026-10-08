import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import ProductCard from '../components/ProductCard'
import { PRODUCTS, SIZES, formatPrice, getProduct, type Size, type SizeStock } from '../data/catalog'
import { useBag } from '../useBag'
import { useChatControl } from '../useChatControl'

const MAX_PER_ORDER = 10

// Approximate swatch colors for the color names used in the catalogue.
const SWATCHES: Record<string, string> = {
  navy: '#1f2a44',
  'navy blue': '#1f2a44',
  white: '#ffffff',
  cream: '#efe6cf',
  ivory: '#f7f3e3',
  gray: '#8a8d91',
  'heather gray': '#9b9da2',
  'light gray': '#c9cbce',
  'dark heather gray': '#5c5e63',
  'charcoal gray': '#3f4246',
  'dark heather charcoal': '#4a4c50',
  'heather charcoal gray': '#55575c',
  black: '#111111',
  red: '#c8102e',
  blue: '#2f5fb3',
  'royal blue': '#2747a8',
  'light blue': '#8fb8e0',
  green: '#2e7d4f',
  yellow: '#f2c230',
  gold: '#c9a227',
  'dusty coral': '#e48b7b',
}

function swatchStyle(color: string) {
  if (color === 'multicolor') {
    return { background: 'conic-gradient(#c8102e, #f2c230, #2e7d4f, #2f5fb3, #c8102e)' }
  }
  return { background: SWATCHES[color] ?? '#777' }
}

function availabilityText(s: SizeStock): string {
  if (s.status === 'sold_out') return 'Sold out'
  if (s.status === 'low_stock') return `Only ${s.qty} left`
  return 'In stock'
}

export default function ProductDetail() {
  const { id = '' } = useParams()
  // ?size=M (e.g. from a chat card or the bag) preselects that size if it's in stock.
  const [params] = useSearchParams()
  const sizeParam = params.get('size')
  const initialSize = SIZES.includes(sizeParam as Size) ? (sizeParam as Size) : null
  // Keyed by id + size so selections reset when moving between products or links.
  return <ProductDetailView key={`${id}:${initialSize}`} id={id} initialSize={initialSize} />
}

function ProductDetailView({ id, initialSize }: { id: string; initialSize: Size | null }) {
  const product = getProduct(id)
  const bag = useBag()
  const { openChat } = useChatControl()
  const [selected, setSelected] = useState<Size | null>(() => {
    const stock = product?.sizes.find((s) => s.size === initialSize)
    return stock && stock.qty > 0 ? stock.size : null
  })
  const [quantity, setQuantity] = useState(1)
  const [notice, setNotice] = useState<{ text: string; added?: boolean } | null>(null)

  if (!product) {
    return (
      <div className="empty">
        <h2>We couldn't find that item</h2>
        <Link to="/products" className="btn btn-primary">
          Back to the catalog
        </Link>
      </div>
    )
  }

  const chosen = product.sizes.find((s) => s.size === selected)
  const maxQuantity = Math.min(chosen?.qty ?? 1, MAX_PER_ORDER)
  const related = PRODUCTS.filter(
    (p) => p.collection === product.collection && p.id !== product.id,
  ).slice(0, 4)

  const chooseSize = (size: Size) => {
    setSelected(size)
    setQuantity(1)
    setNotice(null)
  }

  const inBag = chosen ? (bag.items.find((i) => i.product_id === product.id && i.size === chosen.size)?.quantity ?? 0) : 0

  const addToBag = () => {
    if (!chosen) {
      setNotice({ text: 'Please choose a size first.' })
      return
    }
    const before = inBag
    const after = bag.add(product.id, chosen.size, quantity, chosen.qty)
    setNotice(
      after > before
        ? { text: `Added ${after - before} × ${product.name} (${chosen.size}) to your bag.`, added: true }
        : { text: `Your bag already has all ${after} we have in ${chosen.size}.`, added: true },
    )
  }

  const askAboutThis = () =>
    openChat({
      productName: product.name,
      questions: [
        'What colors does this come in?',
        'Which sizes are in stock?',
        "What's the price?",
        'Show me similar items',
      ],
    })

  return (
    <>
      <nav className="crumbs" aria-label="Breadcrumb">
        <Link to="/">Home</Link> / <Link to="/products">Products Catalog</Link> /{' '}
        <Link to={`/products?collection=${encodeURIComponent(product.collection)}`}>
          {product.collection}
        </Link>{' '}
        / <span>{product.name}</span>
      </nav>

      <article className="pdp">
        <div className="pdp-media">
          <div className="pdp-image">
            <img src={product.image} alt={product.name} />
            {product.badge && <span className="badge badge-large">{product.badge}</span>}
          </div>
        </div>

        <div className="pdp-info">
          <span className="eyebrow">
            {product.category} · {product.collection}
          </span>
          <h1 className="pdp-title">{product.name}</h1>
          <p className="pdp-price">{formatPrice(product.price)}</p>

          <p className="pdp-description">
            {product.description ?? product.shortDescription}
          </p>

          {product.colors.length > 0 && (
            <div className="pdp-block">
              <div className="pdp-label">
                <strong>Colors</strong>
                <span className="muted">{product.colors.length} in this design</span>
              </div>
              <ul className="swatches">
                {product.colors.map((c) => (
                  <li key={c}>
                    <span className="swatch" style={swatchStyle(c)} aria-hidden="true" />
                    {c}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="pdp-block">
            <div className="pdp-label">
              <strong>Size{chosen ? `: ${chosen.size}` : ''}</strong>
              <span className="muted">{product.sizesAvailable} of 6 sizes in stock</span>
            </div>
            <div className="size-buttons">
              {product.sizes.map((s) => (
                <button
                  key={s.size}
                  type="button"
                  className={`size-btn ${s.status}${selected === s.size ? ' selected' : ''}`}
                  disabled={s.status === 'sold_out'}
                  onClick={() => chooseSize(s.size)}
                  aria-pressed={selected === s.size}
                  title={availabilityText(s)}
                >
                  {s.size}
                </button>
              ))}
            </div>
            <p className="stock-note">
              {!chosen && 'Pick a size to check availability.'}
              {chosen?.status === 'low_stock' && (
                <span className="low-stock">
                  Only {chosen.qty} left in {chosen.size}. Grab it soon.
                </span>
              )}
              {chosen?.status === 'in_stock' && `${chosen.size} is in stock at Campus Customs.`}
            </p>
          </div>

          <div className="pdp-buy">
            <div className="qty" aria-label="Quantity">
              <button
                type="button"
                onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                disabled={quantity <= 1}
                aria-label="Decrease quantity"
              >
                −
              </button>
              <span aria-live="polite">{quantity}</span>
              <button
                type="button"
                onClick={() => setQuantity((q) => Math.min(maxQuantity, q + 1))}
                disabled={!chosen || quantity >= maxQuantity}
                aria-label="Increase quantity"
              >
                +
              </button>
            </div>
            <button type="button" className="btn btn-primary pdp-add" onClick={addToBag}>
              {chosen ? `Add to bag · ${formatPrice(product.price * quantity)}` : 'Select a size'}
            </button>
          </div>
          {notice && (
            <p className="form-note">
              {notice.text}{' '}
              {notice.added && (
                <Link to="/bag" className="note-link">
                  View bag →
                </Link>
              )}
            </p>
          )}
          {inBag > 0 && !notice && (
            <p className="muted small">
              {inBag} in your bag in {chosen?.size}. <Link to="/bag">View bag</Link>
            </p>
          )}

          <button type="button" className="btn btn-ghost btn-block ask-about" onClick={askAboutThis}>
            Ask about this item
          </button>

          <div className="pdp-accordions">
            <details open>
              <summary>Product details</summary>
              <dl className="spec-list">
                <dt>Style</dt>
                <dd className="capitalize">{product.garmentType}</dd>
                <dt>Category</dt>
                <dd>{product.category}</dd>
                <dt>Collection</dt>
                <dd>{product.collection}</dd>
                {product.colors.length > 0 && (
                  <>
                    <dt>Colors</dt>
                    <dd className="capitalize">{product.colors.join(', ')}</dd>
                  </>
                )}
                <dt>Item #</dt>
                <dd>{product.id}</dd>
              </dl>
            </details>

            <details>
              <summary>Size availability</summary>
              <table className="stock-table">
                <tbody>
                  {product.sizes.map((s) => (
                    <tr key={s.size} className={s.status}>
                      <th scope="row">{s.size}</th>
                      <td>{availabilityText(s)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>

            <details>
              <summary>Made in New Haven</summary>
              <p className="muted">
                Campus Customs designs, screen-prints and embroiders its gear at 57 Broadway, right
                across from campus. Stop by to try on sizes before you buy.
              </p>
            </details>

            {product.tags.length > 0 && (
              <details>
                <summary>Tags</summary>
                <div className="chips">
                  {product.tags.map((t) => (
                    <Link key={t} to={`/products?q=${encodeURIComponent(t)}`} className="chip chip-link">
                      {t}
                    </Link>
                  ))}
                </div>
              </details>
            )}
          </div>
        </div>
      </article>

      {related.length > 0 && (
        <section className="section">
          <div className="section-head">
            <h2>More from {product.collection}</h2>
            <Link
              to={`/products?collection=${encodeURIComponent(product.collection)}`}
              className="link-arrow"
            >
              View all →
            </Link>
          </div>
          <div className="grid">
            {related.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </section>
      )}
    </>
  )
}
