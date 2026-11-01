import { onAuthStateChanged, type User } from 'firebase/auth'
import { useEffect, useState, type ReactNode } from 'react'
import { AuthContext } from '@/auth/auth-context'
import { auth } from '@/lib/firebase'

/**
 * Tracks the signed-in Firebase user. `loading` stays true until Firebase has restored any
 * existing session, so we never flash the login page (or fire API calls) too early.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(
    () =>
      onAuthStateChanged(auth, (next) => {
        setUser(next)
        setLoading(false)
      }),
    [],
  )

  return <AuthContext value={{ user, loading }}>{children}</AuthContext>
}
