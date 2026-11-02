import { BAND_STYLE } from '@/components/upload-detail/band-style'
import { ConfidenceBadge } from '@/components/upload-detail/ConfidenceBadge'
import { TableCell, TableRow } from '@/components/ui/table'
import { band } from '@/lib/confidence'
import { formatBytes, formatTimestamp } from '@/lib/format'
import type { EntrySummary } from '@/lib/types'
import { cn } from '@/lib/utils'

/** The URL without its host, which has its own column: "https://x.example/a/b?c" → "/a/b?c". */
function pathOf(entry: EntrySummary): string {
  if (!entry.url) return ''
  const withoutScheme = entry.url.replace(/^[a-z]+:\/\//i, '')
  return entry.host && withoutScheme.startsWith(entry.host) ? withoutScheme.slice(entry.host.length) || '/' : withoutScheme
}

type Props = { entry: EntrySummary; selected: boolean; onOpen: () => void }

/**
 * One log entry. A flagged row is tinted, has a left bar in its band's colour, and says
 * "High 95%", so it stands out without relying on colour alone. Clicking opens the details.
 */
export function EntryRow({ entry, selected, onOpen }: Props) {
  const flagged = entry.anomaly_confidence !== null
  const bandColor = flagged ? BAND_STYLE[band(entry.anomaly_confidence!)].color : 'transparent'

  return (
    <TableRow
      onClick={onOpen}
      aria-selected={selected}
      className={cn('cursor-pointer', selected && 'bg-muted!')}
      style={flagged ? { background: `color-mix(in oklch, ${bandColor} 7%, transparent)` } : undefined}
    >
      <TableCell className="border-l-4 font-mono text-xs whitespace-nowrap tabular-nums" style={{ borderLeftColor: bandColor }}>
        {/* A real button so keyboard users can open the details: Enter "clicks" it, and the click
            reaches the row's handler. */}
        <button type="button" className="text-left hover:underline">
          {formatTimestamp(entry.ts)}
        </button>
      </TableCell>
      <TableCell className="max-w-48 truncate" title={entry.login ?? undefined}>
        {entry.login ?? '—'}
      </TableCell>
      <TableCell className="whitespace-nowrap">
        <span className={cn(entry.action === 'Blocked' && 'font-medium text-[var(--viz-blocked)]')}>{entry.action ?? '—'}</span>
        <span className="ml-1.5 text-xs text-muted-foreground tabular-nums">{entry.respcode ?? ''}</span>
      </TableCell>
      <TableCell className="max-w-96">
        <div className="truncate" title={entry.url ?? undefined}>
          <span className="text-xs text-muted-foreground">{entry.reqmethod} </span>
          <span className="font-medium">{entry.host}</span>
          <span className="text-muted-foreground">{pathOf(entry)}</span>
        </div>
      </TableCell>
      <TableCell className="text-right whitespace-nowrap tabular-nums">{entry.reqsize !== null ? formatBytes(entry.reqsize) : '—'}</TableCell>
      <TableCell>{flagged && <ConfidenceBadge confidence={entry.anomaly_confidence!} />}</TableCell>
    </TableRow>
  )
}
