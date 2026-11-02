import { BrainCircuit, ChartNoAxesColumn, ListChecks, type LucideIcon } from 'lucide-react'
import { Link } from 'react-router'
import { DETECTOR_NAMES, formatConfidence } from '@/lib/confidence'
import { formatCount } from '@/lib/format'
import type { Anomaly } from '@/lib/types'

const DETECTOR_ICONS: Record<Anomaly['detector'], LucideIcon> = {
  rule: ListChecks,
  statistical: ChartNoAxesColumn,
  ml: BrainCircuit,
}

/** One piece of evidence: which kind of detector, what it found (in a sentence), how sure, and a link to its entries. */
export function AnomalyItem({ anomaly }: { anomaly: Anomaly }) {
  const Icon = DETECTOR_ICONS[anomaly.detector]
  return (
    <li className="grid gap-1 border-l-2 pl-3">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
          <Icon className="size-3.5" aria-hidden />
          {DETECTOR_NAMES[anomaly.detector]}
        </span>
        <span className="font-medium">{anomaly.title}</span>
        <span className="text-xs text-muted-foreground tabular-nums">
          {formatConfidence(anomaly.confidence)} ·{' '}
          <Link to={{ search: `?tab=entries&anomaly=${anomaly.id}` }} className="underline-offset-2 hover:text-foreground hover:underline">
            {formatCount(anomaly.entry_count)} {anomaly.entry_count === 1 ? 'entry' : 'entries'}
          </Link>
        </span>
      </div>
      <p className="text-muted-foreground">{anomaly.explanation}</p>
    </li>
  )
}
