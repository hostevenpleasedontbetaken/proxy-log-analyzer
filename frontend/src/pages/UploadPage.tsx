import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { AppHeader } from '@/components/AppHeader'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { OverviewTab } from '@/components/upload-detail/overview/OverviewTab'
import { UploadHeading } from '@/components/upload-detail/UploadHeading'
import { ApiError, api } from '@/lib/api'
import type { UploadDetail } from '@/lib/types'

/** One upload's analysis. */
export function UploadPage() {
  const { uploadId = '' } = useParams()
  const upload = useQuery({
    queryKey: ['upload', uploadId],
    queryFn: () => api<UploadDetail>(`/uploads/${uploadId}`),
    staleTime: Infinity, // an analysis never changes once stored
  })

  return (
    <>
      <AppHeader />
      <main className="mx-auto grid max-w-6xl gap-6 p-4 sm:p-6">
        <Link to="/uploads" className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" aria-hidden />
          All uploads
        </Link>
        {upload.isPending && <p className="text-muted-foreground">Loading…</p>}
        {upload.isError && (
          <Alert variant="destructive">
            <AlertDescription>
              {upload.error instanceof ApiError && upload.error.status === 404
                ? "This upload doesn't exist, or it isn't yours."
                : `Couldn't load this upload: ${upload.error.message}`}
            </AlertDescription>
          </Alert>
        )}
        {upload.data && (
          <>
            <UploadHeading upload={upload.data} />
            <OverviewTab upload={upload.data} />
          </>
        )}
      </main>
    </>
  )
}
