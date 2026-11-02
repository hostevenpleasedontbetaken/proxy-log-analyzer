import { AppHeader } from '@/components/AppHeader'
import { ServerStatus } from '@/components/ServerStatus'
import { UploadCard } from '@/components/UploadCard'
import { UploadsList } from '@/components/UploadsList'

/** Home page: upload a log (or a sample) and pick one of your past uploads. */
export function UploadsPage() {
  return (
    <>
      <AppHeader />
      <main className="mx-auto grid max-w-6xl gap-6 p-4 sm:p-6">
        <ServerStatus />
        <UploadCard />
        <UploadsList />
      </main>
    </>
  )
}
