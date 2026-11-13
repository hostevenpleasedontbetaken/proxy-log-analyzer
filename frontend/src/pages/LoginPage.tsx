import { signInWithEmailAndPassword } from 'firebase/auth'
import { useState, type FormEvent } from 'react'
import { Navigate, useLocation } from 'react-router'
import { useAuth } from '@/auth/auth-context'
import { loginErrorMessage } from '@/auth/login-errors'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { auth } from '@/lib/firebase'

export function LoginPage() {
  const { user } = useAuth()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (user) {
    const from = (location.state as { from?: string } | null)?.from ?? '/uploads'
    return <Navigate to={from} replace />
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await signInWithEmailAndPassword(auth, email, password)
      // AuthProvider sees the new user and this page re-renders into the <Navigate> above.
    } catch (err) {
      setError(loginErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="grid min-h-svh place-items-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Proxy Log Analyzer</CardTitle>
          <CardDescription>Sign in to upload and analyze Zscaler web logs.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
