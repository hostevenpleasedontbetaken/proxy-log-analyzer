import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatBucket, formatBytes, formatCount } from '@/lib/format'
import type { TimelineBucket } from '@/lib/types'

/** The timeline's numbers as a table, for screen readers and anyone who prefers exact values. */
export function TimelineTable({ buckets, multiDay }: { buckets: TimelineBucket[]; multiDay: boolean }) {
  return (
    <div className="max-h-72 overflow-y-auto">
      <Table>
        <TableHeader className="sticky top-0 bg-card">
          <TableRow>
            <TableHead>Start (UTC)</TableHead>
            <TableHead className="text-right">Allowed</TableHead>
            <TableHead className="text-right">Blocked</TableHead>
            <TableHead className="text-right">Flagged</TableHead>
            <TableHead className="text-right">Uploaded</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody className="tabular-nums">
          {buckets.map((bucket) => (
            <TableRow key={bucket.t}>
              <TableCell>{formatBucket(bucket.t, multiDay)}</TableCell>
              <TableCell className="text-right">{formatCount(bucket.allowed)}</TableCell>
              <TableCell className="text-right">{formatCount(bucket.blocked)}</TableCell>
              <TableCell className="text-right">{formatCount(bucket.flagged)}</TableCell>
              <TableCell className="text-right">{formatBytes(bucket.bytes_out)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
