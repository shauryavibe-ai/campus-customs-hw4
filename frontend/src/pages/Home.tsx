import { Link } from 'react-router-dom'
import ProductCard from '../components/ProductCard'
import { COLLECTIONS, PRODUCTS, getProduct, type Collection } from '../data/catalog'

const FEATURED_IDS = [
  'basic-hoodie-big-yale',
  '2025-yale-vs-harvard-t-shirt',
  'district-vit-hoodie-vintage-sailor-bulldog',
  'boola-boola-t-shirt',
]

const COLLECTION_COPY: Record<Collection, { blurb: string; cover: string }> = {
  'Residential Colleges': {
    blurb: 'Your college crest, your home base.',
    cover: 'saybrook-college-crewneck',
  },
  Athletics: {
    blurb: 'From the Bowl to the boathouse.',
    cover: 'yale-sports-hoodie-hockey',
  },
  'Graduate & Professional Schools': {
    blurb: 'Law, Medicine, SOM, Art and more.',
    cover: 'school-of-management-crest-t-shirt',
  },
  'Yale Family': {
    blurb: 'For everyone cheering from the stands.',
    cover: 'yale-mom-crewneck',
  },
  'Classic Yale': {
    blurb: 'Timeless marks and vintage Bulldogs.',
    cover: 'champion-reverse-weave-crewneck',
  },
}

export default function Home() {
  const featured = FEATURED_IDS.map(getProduct).filter((p) => p !== undefined)
  const countFor = (c: Collection) => PRODUCTS.filter((p) => p.collection === c).length

  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow">New Haven's Yale outfitter since the 1970s</span>
          <h1>
            Rep the Blue.
            <br />
            <span className="accent">Straight from Broadway.</span>
          </h1>
          <p className="lede">
            Hoodies, crewnecks, quarter-zips and tees for students, alumni and every proud Yale
            family. Printed and stitched right across from campus.
          </p>
          <div className="hero-actions">
            <Link to="/products" className="btn btn-primary">
              Shop the catalog
            </Link>
            <Link to="/about" className="btn btn-ghost">
              Our story
            </Link>
          </div>
        </div>
        <div className="hero-art" aria-hidden="true">
          {featured.slice(0, 3).map((p, i) => (
            <div key={p.id} className={`hero-tile hero-tile-${i}`}>
              <img src={p.image} alt="" />
            </div>
          ))}
        </div>
      </section>

      <section className="perks">
        <div>
          <strong>Printed on site</strong>
          <span className="muted">Screen printing &amp; embroidery in New Haven</span>
        </div>
        <div>
          <strong>Every college, every team</strong>
          <span className="muted">{PRODUCTS.length} styles across {COLLECTIONS.length} collections</span>
        </div>
        <div>
          <strong>Live stock by size</strong>
          <span className="muted">See exactly what's on the shelf, XS to XXL</span>
        </div>
      </section>

      <section className="section">
        <div className="section-head">
          <h2>Shop by collection</h2>
          <Link to="/products" className="link-arrow">
            View all →
          </Link>
        </div>
        <div className="collections">
          {COLLECTIONS.map((c) => (
            <Link
              key={c}
              to={`/products?collection=${encodeURIComponent(c)}`}
              className="collection-tile"
            >
              <img src={getProduct(COLLECTION_COPY[c].cover)?.image} alt="" />
              <div className="collection-info">
                <h3>{c}</h3>
                <p>{COLLECTION_COPY[c].blurb}</p>
                <span className="muted">{countFor(c)} styles</span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section-head">
          <h2>Bulldog favorites</h2>
          <Link to="/products" className="link-arrow">
            Shop all →
          </Link>
        </div>
        <div className="grid">
          {featured.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      </section>

      <section className="banner">
        <div>
          <h2>The whole family bleeds blue.</h2>
          <p className="lede">
            Mom, Dad, Grandpa, Aunt, Cousin: there's a Yale crewneck or hoodie for everyone who
            made it to Move-In Day.
          </p>
        </div>
        <Link to="/products?collection=Yale%20Family" className="btn btn-primary">
          Shop Yale Family
        </Link>
      </section>
    </>
  )
}
