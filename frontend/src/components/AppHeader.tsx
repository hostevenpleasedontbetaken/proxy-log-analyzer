import { signOut } from 'firebase/auth'
import { ShieldCheck } from 'lucide-react'
import { Link } from 'react-router'
import { useAuth } from '@/auth/auth-context'
import { Button } from '@/components/ui/button'
import { auth } from '@/lib/firebase'

/** Top bar on every signed-in page: app name (links home), who's signed in, sign out. */
export function AppHeader() {
  const { user } = useAuth()

  return (
    <header className="border-b">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4">
        <Link to="/uploads" className="flex items-center gap-2 font-semibold">
          <ShieldCheck className="size-5" aria-hidden />
          Proxy Log Analyzer
        </Link>
        <div className="flex items-center gap-3 text-sm">
          <span className="hidden text-muted-foreground sm:inline">
            {user?.isAnonymous ? 'Guest (read-only demo)' : user?.email}
          </span>
          <Button variant="outline" size="sm" onClick={() => signOut(auth)}>
            {user?.isAnonymous ? 'Sign in' : 'Sign out'}
          </Button>
        </div>
      </div>
    </header>
  )
}
