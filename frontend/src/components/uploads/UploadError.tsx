import { Link } from 'react-router'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ApiError } from '@/lib/api'

/** Why an upload failed. A duplicate links to the analysis that already exists. */
export function UploadError({ error }: { error: Error | string | null }) {
  if (!error) return null
  const message = typeof error === 'string' ? error : error.message
  const existing =
    error instanceof ApiError && error.code === 'duplicate_upload' ? error.details.existing_upload_id : null

  return (
    <Alert variant="destructive">
      <AlertDescription>
        <span>
          {message}
          {typeof existing === 'string' && (
            <>
              {' '}
              <Link to={`/uploads/${existing}`} className="font-medium underline underline-offset-4">
                Open it
              </Link>
            </>
          )}
        </span>
      </AlertDescription>
    </Alert>
  )
}
