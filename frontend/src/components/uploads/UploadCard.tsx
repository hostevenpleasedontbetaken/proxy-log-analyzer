import { useMutation, useQueryClient } from '@tanstack/react-query'
import { FileUp, LoaderCircle } from 'lucide-react'
import { useState } from 'react'
import { useDropzone, type FileRejection } from 'react-dropzone'
import { useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { UploadError } from '@/components/uploads/UploadError'
import { UploadProgress } from '@/components/uploads/UploadProgress'
import { formatBytes } from '@/lib/format'
import { loadSample, SAMPLES, type Sample } from '@/lib/samples'
import { uploadLog } from '@/lib/upload'
import { cn } from '@/lib/utils'

/** Same limit as the backend (MAX_CONTENT_LENGTH); checked here too so big files fail fast. */
export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024

/** Turns react-dropzone's rejection codes into a message for the user. */
function rejectionMessage(rejections: FileRejection[]): string {
  if (rejections.length > 1) return 'Upload one file at a time.'
  const tooBig = rejections[0]?.errors.some((e) => e.code === 'file-too-large')
  if (tooBig) return `That file is over ${formatBytes(MAX_UPLOAD_BYTES)}. Gzip it (logs compress ~20×) and try again.`
  return rejections[0]?.errors[0]?.message ?? "That file can't be uploaded."
}

/**
 * Drop a log (or pick a sample) → upload with progress → "Analyzing…" while the server parses
 * and runs detection → open the new upload. One file at a time.
 */
export function UploadCard() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [progress, setProgress] = useState(0)
  const [loadingSample, setLoadingSample] = useState<string | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)

  const upload = useMutation({
    mutationFn: (file: File) => uploadLog(file, setProgress),
    onSuccess: (detail) => {
      // The response is the full upload, so the next page can render without refetching.
      queryClient.setQueryData(['upload', detail.id], detail)
      void queryClient.invalidateQueries({ queryKey: ['uploads'] })
      void navigate(`/uploads/${detail.id}`)
    },
  })
  const busy = upload.isPending || loadingSample !== null

  function start(file: File) {
    setLocalError(null)
    setProgress(0)
    upload.mutate(file)
  }

  async function startSample(sample: Sample) {
    setLocalError(null)
    upload.reset()
    setLoadingSample(sample.filename)
    try {
      start(await loadSample(sample))
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoadingSample(null)
    }
  }

  const dropzone = useDropzone({
    multiple: false,
    maxSize: MAX_UPLOAD_BYTES,
    disabled: busy,
    onDropAccepted: ([file]) => start(file),
    onDropRejected: (rejections) => {
      upload.reset()
      setLocalError(rejectionMessage(rejections))
    },
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Analyze a log</CardTitle>
        <CardDescription>
          Zscaler NSS web logs as JSON lines, plain or gzipped, up to {formatBytes(MAX_UPLOAD_BYTES)}.
        </CardDescription>
        <p className="text-sm text-muted-foreground">
          Demo site: please use the samples below, not real logs. Uploads are deleted after 7 days.
        </p>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div
          {...dropzone.getRootProps({
            className: cn(
              'grid min-h-36 cursor-pointer place-items-center rounded-lg border-2 border-dashed p-6 text-center text-sm transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              dropzone.isDragActive ? 'border-primary bg-muted' : 'border-border hover:bg-muted/50',
              busy && 'cursor-default opacity-80',
            ),
          })}
        >
          <input {...dropzone.getInputProps()} aria-label="Log file" />
          {upload.isPending ? (
            <UploadProgress progress={progress} />
          ) : (
            <div className="grid justify-items-center gap-2">
              <FileUp className="size-6 text-muted-foreground" aria-hidden />
              <p>
                <span className="font-medium">Drop a log file here</span> or click to choose one
              </p>
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted-foreground">No log handy? Try a sample:</span>
          {SAMPLES.map((sample) => (
            <Button
              key={sample.filename}
              variant="outline"
              size="sm"
              title={sample.description}
              disabled={busy}
              onClick={() => void startSample(sample)}
            >
              {loadingSample === sample.filename && <LoaderCircle className="animate-spin" aria-hidden />}
              {sample.label}
            </Button>
          ))}
        </div>

        <UploadError error={localError ?? upload.error} />
      </CardContent>
    </Card>
  )
}
