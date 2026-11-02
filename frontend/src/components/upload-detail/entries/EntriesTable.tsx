import { EntryRow } from '@/components/upload-detail/entries/EntryRow'
import { Table, TableBody, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { EntrySummary } from '@/lib/types'

type Props = { entries: EntrySummary[]; selectedLine: number | null; onOpen: (lineNo: number) => void }

/** One page of log entries, oldest first. */
export function EntriesTable({ entries, selectedLine, onOpen }: Props) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Time (UTC)</TableHead>
          <TableHead>User</TableHead>
          <TableHead>Action</TableHead>
          <TableHead>Request</TableHead>
          <TableHead className="text-right">Sent</TableHead>
          <TableHead>Flagged</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entries.map((entry) => (
          <EntryRow key={entry.line_no} entry={entry} selected={entry.line_no === selectedLine} onOpen={() => onOpen(entry.line_no)} />
        ))}
      </TableBody>
    </Table>
  )
}
