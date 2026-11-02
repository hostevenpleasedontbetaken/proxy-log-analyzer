import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { AppHeader } from '@/components/AppHeader'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ApiError, api } from '@/lib/api'
import { formatCount, formatTimeRange } from '@/lib/format'
import type { UploadDetail } from '@/lib/types'

/** One upload's analysis. This PR adds the page and its header; the tabs follow. */
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
        {upload.data && <UploadHeading upload={upload.data} />}
      </main>
    </>
  )
}

function UploadHeading({ upload }: { upload: UploadDetail }) {
  return (
    <div className="grid gap-1">
      <h1 className="text-xl font-semibold break-all">{upload.filename}</h1>
      <p className="text-sm text-muted-foreground">
        {formatCount(upload.parsed_count ?? 0)} entries · {formatTimeRange(upload.time_start, upload.time_end)}
        {!!upload.error_count && ` · ${formatCount(upload.error_count)} lines skipped`}
      </p>
    </div>
  )
}
