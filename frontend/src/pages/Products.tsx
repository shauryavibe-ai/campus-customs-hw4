import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import ProductCard from '../components/ProductCard'
import {
  CATEGORIES,
  COLLECTIONS,
  COLOR_FAMILIES,
  PRODUCTS,
  SIZES,
  matchesSearch,
} from '../data/catalog'

const SORTS = {
  featured: 'Featured',
  'price-asc': 'Price: low to high',
  'price-desc': 'Price: high to low',
  name: 'Name: A to Z',
} as const
type SortKey = keyof typeof SORTS

export default function Products() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const category = params.get('category') ?? ''
  const collection = params.get('collection') ?? ''
  const color = params.get('color') ?? ''
  const size = params.get('size') ?? ''
  const sort = (params.get('sort') ?? 'featured') as SortKey

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const results = useMemo(() => {
    const filtered = PRODUCTS.filter(
      (p) =>
        matchesSearch(p, q) &&
        (!category || p.category === category) &&
        (!collection || p.collection === collection) &&
        (!color || p.colorFamily === color) &&
        (!size || p.sizes.some((s) => s.size === size && s.status !== 'sold_out')),
    )
    if (sort === 'price-asc') return [...filtered].sort((a, b) => a.price - b.price)
    if (sort === 'price-desc') return [...filtered].sort((a, b) => b.price - a.price)
    if (sort === 'name') return [...filtered].sort((a, b) => a.name.localeCompare(b.name))
    return filtered
  }, [q, category, collection, color, size, sort])

  const hasFilters = Boolean(q || category || collection || color || size)

  return (
    <div className="catalog">
      <div className="page-head">
        <span className="eyebrow">Products Catalog</span>
        <h1>{collection || category || 'Shop all Bulldog gear'}</h1>
        <p className="muted">
          {results.length} of {PRODUCTS.length} styles · stock shown live by size
        </p>
      </div>

      <div className="category-pills" role="tablist" aria-label="Category">
        <button className={`pill${!category ? ' pill-active' : ''}`} onClick={() => setParam('category', '')}>
          All
        </button>
        {CATEGORIES.map((c) => (
          <button
            key={c}
            className={`pill${category === c ? ' pill-active' : ''}`}
            onClick={() => setParam('category', category === c ? '' : c)}
          >
            {c}
          </button>
        ))}
      </div>

      <div className="filters">
        <input
          type="search"
          placeholder="Search bulldog, hockey, Saybrook…"
          value={q}
          onChange={(e) => setParam('q', e.target.value)}
          aria-label="Search products"
        />
        <select value={collection} onChange={(e) => setParam('collection', e.target.value)} aria-label="Collection">
          <option value="">All collections</option>
          {COLLECTIONS.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <select value={color} onChange={(e) => setParam('color', e.target.value)} aria-label="Color">
          <option value="">Any color</option>
          {COLOR_FAMILIES.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <select value={size} onChange={(e) => setParam('size', e.target.value)} aria-label="In stock in size">
          <option value="">Any size</option>
          {SIZES.map((s) => (
            <option key={s} value={s}>
              In stock in {s}
            </option>
          ))}
        </select>
        <select value={sort} onChange={(e) => setParam('sort', e.target.value)} aria-label="Sort">
          {Object.entries(SORTS).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
        {hasFilters && (
          <button className="btn btn-ghost btn-small" onClick={() => setParams({}, { replace: true })}>
            Clear
          </button>
        )}
      </div>

      {results.length > 0 ? (
        <div className="grid">
          {results.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      ) : (
        <div className="empty">
          <h3>No matches yet</h3>
          <p className="muted">Try a different search or clear your filters.</p>
        </div>
      )}
    </div>
  )
}
