import { Link } from 'react-router-dom'
import { formatPrice, type Product } from '../data/catalog'

// Non-breaking hyphens keep words like "T-Shirt" and "¼-Zip" on one line.
const keepHyphensTogether = (text: string) => text.replace(/-/g, '\u2011')

export default function ProductCard({ product }: { product: Product }) {
  return (
    <Link to={`/products/${product.id}`} className="card">
      <div className="card-image">
        <img src={product.image} alt={product.name} loading="lazy" />
        {product.badge && <span className="badge">{product.badge}</span>}
      </div>
      <div className="card-body">
        <span className="card-category">{product.category}</span>
        <div className="card-heading">
          <h3 className="card-title">{keepHyphensTogether(product.name)}</h3>
          <span className="price">{formatPrice(product.price)}</span>
        </div>
        <p className="card-description">{product.shortDescription}</p>
        <div className="card-footer">
          <span className="size-dots" aria-label={`${product.sizesAvailable} of 6 sizes in stock`}>
            {product.sizes.map((s) => (
              <span key={s.size} className={`size-dot ${s.status}`} title={`${s.size}: ${s.status.replace('_', ' ')}`}>
                {s.size}
              </span>
            ))}
          </span>
          <span className="card-link">View details →</span>
        </div>
      </div>
    </Link>
  )
}
