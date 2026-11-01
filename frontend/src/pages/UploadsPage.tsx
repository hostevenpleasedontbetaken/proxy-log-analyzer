import { useQuery } from '@tanstack/react-query'
import { signOut } from 'firebase/auth'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { auth } from '@/lib/firebase'

type Me = { uid: string; email: string | null }

/** M0 placeholder: proves the login → token → Flask round-trip. Replaced in M6. */
export function UploadsPage() {
  const me = useQuery({ queryKey: ['me'], queryFn: () => api<Me>('/me') })

  return (
    <main className="mx-auto grid max-w-2xl gap-4 p-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Uploads</h1>
        <Button variant="outline" onClick={() => signOut(auth)}>
          Sign out
        </Button>
      </header>
      {me.isPending && <p className="text-muted-foreground">Checking the API…</p>}
      {me.isError && <p className="text-destructive">API error: {me.error.message}</p>}
      {me.data && (
        <p data-testid="api-hello">
          API says hello, <span className="font-mono">{me.data.email ?? me.data.uid}</span>
        </p>
      )}
    </main>
  )
}
