import { useEffect, useState, type ReactNode } from 'react'
import * as api from './api'
import { AuthContext, type AuthState } from './useAuth'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<api.User | null>(null)
  const [loading, setLoading] = useState(true)

  // The session lives in an HttpOnly cookie; ask the server who (if anyone) is logged in.
  useEffect(() => {
    api.currentUser().then((u) => {
      setUser(u)
      setLoading(false)
    })
  }, [])

  const value: AuthState = {
    user,
    loading,
    login: async (email, password) => {
      const u = await api.login(email, password)
      setUser(u)
      return u
    },
    signup: async (input) => {
      const u = await api.signup(input)
      setUser(u)
      return u
    },
    logout: async () => {
      await api.logout().catch(() => undefined)
      setUser(null)
    },
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
