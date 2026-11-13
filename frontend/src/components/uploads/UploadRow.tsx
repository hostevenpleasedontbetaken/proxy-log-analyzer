import type { MouseEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { TableCell, TableRow } from '@/components/ui/table'
import { DeleteUploadButton } from '@/components/uploads/DeleteUploadButton'
import { formatBytes, formatCount, formatDateTime, formatTimeRange } from '@/lib/format'
import type { UploadSummary } from '@/lib/types'

/**
 * One upload in the list. Clicking anywhere on the row opens its analysis; the file name is also
 * a real link, for keyboard users and "open in new tab". Less important columns hide on phones.
 */
export function UploadRow({ upload }: { upload: UploadSummary }) {
  const navigate = useNavigate()
  const href = `/uploads/${upload.id}`

  function openUpload(event: MouseEvent<HTMLTableRowElement>) {
    const target = event.target as HTMLElement
    // Ignore the link and delete button (they do their own thing), and clicks inside the delete
    // dialog: it renders elsewhere in the page, but React still bubbles its clicks to this row.
    if (!event.currentTarget.contains(target) || target.closest('a, button')) return
    void navigate(href)
  }

  return (
    <TableRow className="cursor-pointer" onClick={openUpload}>
      <TableCell className="max-w-64">
        <Link to={href} className="block truncate font-medium hover:underline">
          {upload.filename}
        </Link>
        {upload.is_sample && (
          <span className="mr-2 rounded bg-muted px-1.5 py-0.5 text-xs font-medium">Sample</span>
        )}
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
        {!upload.is_sample && <DeleteUploadButton upload={upload} />}
      </TableCell>
    </TableRow>
  )
}
