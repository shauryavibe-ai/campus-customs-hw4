import { createContext, useContext } from 'react'
import type * as api from './api'

export interface AuthState {
  user: api.User | null
  loading: boolean
  login: (email: string, password: string) => Promise<api.User>
  signup: (input: api.SignupInput) => Promise<api.User>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
