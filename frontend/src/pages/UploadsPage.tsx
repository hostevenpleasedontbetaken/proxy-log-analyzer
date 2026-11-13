import { useAuth } from '@/auth/auth-context'
import { AppHeader } from '@/components/AppHeader'
import { ServerStatus } from '@/components/ServerStatus'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { UploadCard } from '@/components/uploads/UploadCard'
import { UploadsList } from '@/components/uploads/UploadsList'

/** Home page: upload a log (or a sample) and pick one of your past uploads. */
export function UploadsPage() {
  const { user } = useAuth()
  const isGuest = !!user?.isAnonymous

  return (
    <>
      <AppHeader />
      <main className="mx-auto grid max-w-6xl gap-6 p-4 sm:p-6">
        <ServerStatus />
        {isGuest ? (
          <Alert>
            <AlertDescription>
              You're browsing a read-only sample analysis. Sign in with an account to upload your own logs.
            </AlertDescription>
          </Alert>
        ) : (
          <UploadCard />
        )}
        <UploadsList />
      </main>
    </>
  )
}
