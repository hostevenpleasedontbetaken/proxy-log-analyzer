import { Link } from 'react-router'
import { ConfidenceBadge } from '@/components/upload-detail/ConfidenceBadge'
import { AnomalyItem } from '@/components/upload-detail/incidents/AnomalyItem'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { SEVERITY_NAMES } from '@/lib/confidence'
import { formatTimeRange } from '@/lib/format'
import type { Incident } from '@/lib/types'

/**
 * One incident: how sure (confidence) and how bad if real (severity), who and when, then each
 * detector's evidence, strongest first.
 */
export function IncidentCard({ incident }: { incident: Incident }) {
  const evidence = [...incident.anomalies].sort((a, b) => b.confidence - a.confidence)

  return (
    <Card role="article" aria-label={incident.title}>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <ConfidenceBadge confidence={incident.confidence} />
          <span className="text-xs text-muted-foreground">{SEVERITY_NAMES[incident.severity]} severity</span>
        </div>
        <CardTitle className="text-base">{incident.title}</CardTitle>
        <CardDescription>
          <span className="font-medium text-foreground">{incident.subject}</span> ·{' '}
          {formatTimeRange(incident.start_ts, incident.end_ts)}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-2">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Why it was flagged ({evidence.length} {evidence.length === 1 ? 'finding' : 'findings'})
        </p>
        <ul aria-label="Evidence" className="grid gap-3">
          {evidence.map((anomaly) => (
            <AnomalyItem key={anomaly.id} anomaly={anomaly} />
          ))}
        </ul>
        <Link to={{ search: `?tab=entries&incident=${incident.id}` }} className="mt-1 w-fit text-sm font-medium hover:underline">
          View this incident's entries →
        </Link>
      </CardContent>
    </Card>
  )
}
