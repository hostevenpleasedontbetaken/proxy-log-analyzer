import { CircleAlert, Info, TriangleAlert, type LucideIcon } from 'lucide-react'
import type { Band } from '@/lib/types'

// Icon + word + colour, so confidence never relies on colour alone.
const BANDS: { band: Band; icon: LucideIcon; color: string }[] = [
  { band: 'High', icon: CircleAlert, color: 'var(--status-high)' },
  { band: 'Medium', icon: TriangleAlert, color: 'var(--status-medium)' },
  { band: 'Low', icon: Info, color: 'var(--muted-foreground)' },
]

/** "7 High · 1 Medium · 4 Low": incidents by confidence band. */
export function IncidentBands({ counts }: { counts: Record<Band, number> }) {
  return (
    <ul className="flex flex-wrap gap-x-3 gap-y-1">
      {BANDS.map(({ band, icon: Icon, color }) => (
        <li key={band} className="flex items-center gap-1">
          <Icon className="size-4" style={{ color }} aria-hidden />
          <span className="font-medium text-foreground tabular-nums">{counts[band]}</span> {band}
        </li>
      ))}
    </ul>
  )
}
