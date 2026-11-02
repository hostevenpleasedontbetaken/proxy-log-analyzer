import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { EntryFilters } from '@/lib/entry-filters'
import { formatTimeRange } from '@/lib/format'
import type { Incident } from '@/lib/types'

type Props = {
  filters: EntryFilters
  /** To name the incident/finding being filtered on, when the Incidents tab already loaded them. */
  incidents: Incident[] | undefined
  onChange: (changes: Partial<EntryFilters>) => void
  onClearAll: () => void
}

/**
 * The filters that arrive from links rather than the filter bar (a time window from the timeline,
 * an incident or a single finding), each removable, plus "Clear filters".
 */
export function FilterChips({ filters, incidents, onChange, onClearAll }: Props) {
  const incident = incidents?.find((i) => i.id === filters.incident)
  const anomaly = incidents?.flatMap((i) => i.anomalies).find((a) => a.id === filters.anomaly)

  const chips: { key: string; label: string; clear: Partial<EntryFilters> }[] = []
  if (filters.from || filters.to) {
    chips.push({ key: 'time', label: formatTimeRange(filters.from ?? null, filters.to ?? null), clear: { from: undefined, to: undefined } })
  }
  if (filters.incident) {
    chips.push({ key: 'incident', label: `Incident: ${incident?.title ?? `#${filters.incident}`}`, clear: { incident: undefined } })
  }
  if (filters.anomaly) {
    chips.push({ key: 'anomaly', label: `Finding: ${anomaly?.title ?? `#${filters.anomaly}`}`, clear: { anomaly: undefined } })
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {chips.map((chip) => (
        <span key={chip.key} className="inline-flex items-center gap-1 rounded-md border bg-muted/50 py-0.5 pr-0.5 pl-2 text-xs">
          {chip.label}
          <Button variant="ghost" size="icon-xs" aria-label={`Remove filter: ${chip.label}`} onClick={() => onChange(chip.clear)}>
            <X />
          </Button>
        </span>
      ))}
      <Button variant="ghost" size="sm" onClick={onClearAll}>
        Clear filters
      </Button>
    </div>
  )
}
