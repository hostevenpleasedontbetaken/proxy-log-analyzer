import { formatCount, formatTimeRange } from '@/lib/format'
import type { UploadDetail } from '@/lib/types'

/** File name, entry count and the log's time range, above the analysis. */
export function UploadHeading({ upload }: { upload: UploadDetail }) {
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
