import { useEffect, useMemo, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../useAuth'
import { useBag } from '../useBag'
import { ChatControlContext, type ChatControl } from '../useChatControl'
import ChatWidget, { type ChatTopic } from './ChatWidget'

const YEAR = new Date().getFullYear()

const MAIN_TABS = [
  { to: '/', label: 'Home', end: true },
  { to: '/products', label: 'Products Catalog', end: false },
  { to: '/about', label: 'About Us', end: false },
]
const GUEST_TABS = [
  { to: '/login', label: 'Login', end: false },
  { to: '/create-account', label: 'Create Account', end: false },
]

export default function Layout() {
  const { pathname } = useLocation()
  const { user } = useAuth()
  const { count } = useBag()

  // The chat's open state lives here so pages ("Ask about this item") can open it.
  const [chatOpen, setChatOpen] = useState(false)
  const [chatTopic, setChatTopic] = useState<{ path: string; topic: ChatTopic } | null>(null)
  const chatControl = useMemo<ChatControl>(
    () => ({
      openChat: (topic) => {
        setChatTopic(topic ? { path: window.location.pathname, topic } : null)
        setChatOpen(true)
      },
    }),
    [],
  )
  // Product-specific questions only show on the page that asked for them.
  const topic = chatTopic && chatTopic.path === pathname ? chatTopic.topic : null

  const tabs = [
    ...MAIN_TABS,
    { to: '/bag', label: count ? `Bag (${count})` : 'Bag', end: false },
    ...(user ? [{ to: '/account', label: `Hi, ${user.first_name ?? 'there'}`, end: false }] : GUEST_TABS),
  ]

  // Start each new page at the top (e.g. after clicking a product low on the grid).
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return (
    <ChatControlContext.Provider value={chatControl}>
      <div className="shell">
        <div className="announcement">
          Made in New Haven · Printed &amp; embroidered at 57 Broadway
        </div>

        <header className="site-header">
          <Link to="/" className="brand" aria-label="Campus Customs home">
            <span className="brand-mark">CC</span>
            <span className="brand-text">
              Campus <em>Customs</em>
            </span>
          </Link>

          <nav className="tabs" aria-label="Main">
            {tabs.map((tab) => (
              <NavLink
                key={tab.to}
                to={tab.to}
                end={tab.end}
                className={({ isActive }) =>
                  `tab${isActive ? ' tab-active' : ''}${tab.to === '/create-account' || tab.to === '/account' ? ' tab-cta' : ''}`
                }
              >
                {tab.label}
              </NavLink>
            ))}
          </nav>
        </header>

        <main className="page">
          <Outlet />
        </main>

        <footer className="site-footer">
          <div className="footer-col">
            <div className="brand-text">
              Campus <em>Customs</em>
            </div>
            <p className="muted">Bulldog gear, made a block from campus.</p>
          </div>
          <div className="footer-col">
            <h4>Visit</h4>
            <p className="muted">
              57 Broadway
              <br />
              New Haven, CT 06511
            </p>
          </div>
          <div className="footer-col">
            <h4>Shop</h4>
            <Link to="/products">All products</Link>
            <Link to="/products?collection=Residential%20Colleges">Residential Colleges</Link>
            <Link to="/products?collection=Athletics">Athletics</Link>
            <Link to="/products?collection=Yale%20Family">Yale Family</Link>
          </div>
          <div className="footer-col">
            <h4>Account</h4>
            {user ? (
              <Link to="/account">My account</Link>
            ) : (
              <>
                <Link to="/login">Login</Link>
                <Link to="/create-account">Create account</Link>
              </>
            )}
            <Link to="/about">Our story</Link>
          </div>
          <p className="footer-legal muted">
            © {YEAR} Campus Customs · Class project demo
          </p>
        </footer>

        {/* Keyed by user so logging in/out (or switching accounts) starts a clean chat */}
        <ChatWidget key={user?.id ?? 'guest'} open={chatOpen} setOpen={setChatOpen} topic={topic} />
      </div>
    </ChatControlContext.Provider>
  )
}
