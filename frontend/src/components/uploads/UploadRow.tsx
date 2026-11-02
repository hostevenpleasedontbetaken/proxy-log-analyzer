import { Link } from 'react-router'
import { TableCell, TableRow } from '@/components/ui/table'
import { DeleteUploadButton } from '@/components/uploads/DeleteUploadButton'
import { formatBytes, formatCount, formatDateTime, formatTimeRange } from '@/lib/format'
import type { UploadSummary } from '@/lib/types'

/** One upload in the list: name links to its analysis; less important columns hide on phones. */
export function UploadRow({ upload }: { upload: UploadSummary }) {
  return (
    <TableRow>
      <TableCell className="max-w-64">
        <Link to={`/uploads/${upload.id}`} className="block truncate font-medium hover:underline">
          {upload.filename}
        </Link>
        <span className="text-xs text-muted-foreground">{formatBytes(upload.size_bytes)}</span>
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {formatCount(upload.parsed_count ?? 0)}
        {!!upload.error_count && (
          <div className="text-xs text-muted-foreground">{formatCount(upload.error_count)} skipped</div>
        )}
      </TableCell>
      <TableCell className="hidden md:table-cell">{formatTimeRange(upload.time_start, upload.time_end)}</TableCell>
      <TableCell className="hidden sm:table-cell">{formatDateTime(upload.created_at)}</TableCell>
      <TableCell>
        <DeleteUploadButton upload={upload} />
      </TableCell>
    </TableRow>
  )
}
