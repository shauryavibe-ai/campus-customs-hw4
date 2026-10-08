import { Link } from 'react-router-dom'

const VALUES = [
  {
    title: 'Made down the street',
    body: 'Our screen printing, embroidery and design all happen under one roof in New Haven, so your crest comes off a press a few blocks from where you will wear it.',
  },
  {
    title: 'Every corner of Yale',
    body: 'Residential colleges, varsity and club teams, graduate and professional schools, and the families who cheer them on. If it is part of Yale, we want it on a sweatshirt.',
  },
  {
    title: 'Family-run, community-first',
    body: 'We are a local, family-run shop. We know our customers by name and still love seeing a new first-year pick out their first Yale hoodie.',
  },
]

export default function About() {
  return (
    <div className="about">
      <section className="page-head">
        <span className="eyebrow">About Us</span>
        <h1>
          Outfitting Bulldogs <span className="accent">since the 1970s.</span>
        </h1>
        <p className="lede">
          Campus Customs started as a small Broadway storefront selling Yale gear to students and
          visitors. Decades later we're still at 57 Broadway, still family-run, and now we design,
          print and embroider most of what we sell right here in New Haven.
        </p>
      </section>

      <section className="values">
        {VALUES.map((v) => (
          <article key={v.title} className="value-card">
            <h3>{v.title}</h3>
            <p className="muted">{v.body}</p>
          </article>
        ))}
      </section>

      <section className="visit">
        <div>
          <h2>Come say hi</h2>
          <p className="lede">
            Stop by the shop on Broadway to try on sizes, browse new drops, or ask about custom
            orders for your team, club or reunion.
          </p>
        </div>
        <div className="visit-card">
          <strong>Campus Customs</strong>
          <span>57 Broadway</span>
          <span>New Haven, CT 06511</span>
          <Link to="/products" className="btn btn-primary">
            Browse the catalog
          </Link>
        </div>
      </section>
    </div>
  )
}
