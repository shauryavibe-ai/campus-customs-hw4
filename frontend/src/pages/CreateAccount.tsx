import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../useAuth'

const MIN_PASSWORD = 8

// Mirrors the server's rules (backend/security.py) so shoppers get instant feedback.
// The server re-checks everything; this is only for convenience.
function passwordChecks(password: string) {
  return [
    { ok: password.length >= MIN_PASSWORD, label: `At least ${MIN_PASSWORD} characters` },
    { ok: /[A-Za-z]/.test(password) && /\d/.test(password), label: 'A letter and a number' },
  ]
}

export default function CreateAccount() {
  const { user, signup } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ firstName: '', lastName: '', email: '', password: '', confirm: '' })
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (user) {
    return (
      <div className="auth">
        <div className="auth-card">
          <span className="eyebrow">Create Account</span>
          <h1>You already have an account</h1>
          <p className="muted">Signed in as {user.email}.</p>
          <div className="auth-actions">
            <Link to="/account" className="btn btn-primary">
              Go to my account
            </Link>
          </div>
        </div>
      </div>
    )
  }

  const update = (key: keyof typeof form) => (e: ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [key]: e.target.value })

  const checks = passwordChecks(form.password)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!checks.every((c) => c.ok)) {
      setError('Please choose a stronger password.')
      return
    }
    if (form.password !== form.confirm) {
      setError("Passwords don't match.")
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      await signup({
        first_name: form.firstName,
        last_name: form.lastName,
        email: form.email,
        password: form.password,
      })
      navigate('/account', { replace: true, state: { welcome: true } })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth">
      <div className="auth-card">
        <span className="eyebrow">Create Account</span>
        <h1>Join the Campus Customs crew</h1>
        <p className="muted">Save your sizes, track favorites, and get first dibs on new drops.</p>

        <form onSubmit={onSubmit} className="form">
          <div className="form-row">
            <label>
              First name
              <input required maxLength={50} autoComplete="given-name" value={form.firstName} onChange={update('firstName')} />
            </label>
            <label>
              Last name
              <input required maxLength={50} autoComplete="family-name" value={form.lastName} onChange={update('lastName')} />
            </label>
          </div>
          <label>
            Email
            <input
              type="email"
              required
              autoComplete="email"
              value={form.email}
              onChange={update('email')}
              placeholder="you@yale.edu"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              required
              maxLength={128}
              autoComplete="new-password"
              value={form.password}
              onChange={update('password')}
              placeholder={`At least ${MIN_PASSWORD} characters`}
            />
          </label>
          {form.password && (
            <ul className="password-checks" aria-label="Password requirements">
              {checks.map((c) => (
                <li key={c.label} className={c.ok ? 'ok' : ''}>
                  {c.ok ? '✓' : '○'} {c.label}
                </li>
              ))}
            </ul>
          )}
          <label>
            Confirm password
            <input
              type="password"
              required
              autoComplete="new-password"
              value={form.confirm}
              onChange={update('confirm')}
            />
          </label>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
            {submitting ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="muted small">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  )
}
