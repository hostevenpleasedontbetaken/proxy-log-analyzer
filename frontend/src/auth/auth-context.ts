import type { User } from 'firebase/auth'
import { createContext, use } from 'react'

export type AuthState = { user: User | null; loading: boolean }

export const AuthContext = createContext<AuthState>({ user: null, loading: true })

export function useAuth(): AuthState {
  return use(AuthContext)
}
