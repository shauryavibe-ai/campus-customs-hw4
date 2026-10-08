import { useEffect, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../useAuth'

function memberSince(createdAt: string): string {
  // created_at is stored in UTC as "YYYY-MM-DD HH:MM:SS".
  const date = new Date(`${createdAt.replace(' ', 'T')}Z`)
  return Number.isNaN(date.getTime())
    ? createdAt
    : date.toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' })
}

export default function Account() {
  const { user, loading, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  // Show the welcome once, right after signup, then clear it so a reload says "Hi" instead.
  const [welcome] = useState(() => Boolean((location.state as { welcome?: boolean } | null)?.welcome))
  useEffect(() => {
    if (welcome) navigate(location.pathname, { replace: true, state: null })
  }, [welcome, navigate, location.pathname])

  if (loading) return <div className="empty muted">Loading your account…</div>
  if (!user) return <Navigate to="/login" replace state={{ from: '/account' }} />

  const onLogout = async () => {
    // Leave the page first; otherwise the logged-out account page redirects to /login.
    navigate('/', { replace: true })
    await logout()
  }

  return (
    <div className="auth">
      <div className="auth-card auth-card-wide">
        <span className="eyebrow">My Account</span>
        <h1>{welcome ? `Welcome to the crew, ${user.first_name}!` : `Hi, ${user.first_name ?? user.name}`}</h1>
        <p className="muted">
          {welcome ? 'Your account is ready.' : 'Good to see you again.'}
        </p>

        <dl className="spec-list account-details">
          <dt>Name</dt>
          <dd>{user.name}</dd>
          <dt>Email</dt>
          <dd>{user.email}</dd>
          <dt>Member since</dt>
          <dd>{memberSince(user.created_at)}</dd>
        </dl>

        <div className="auth-actions">
          <Link to="/products" className="btn btn-primary">
            Shop the catalog
          </Link>
          <button type="button" className="btn btn-ghost" onClick={onLogout}>
            Log out
          </button>
        </div>
      </div>
    </div>
  )
}
