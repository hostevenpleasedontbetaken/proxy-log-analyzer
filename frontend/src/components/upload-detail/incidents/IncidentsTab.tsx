import { useSearchParams } from 'react-router'
import { BANDS } from '@/components/upload-detail/band-style'
import { useIncidents } from '@/components/upload-detail/useIncidents'
import { BandFilter } from '@/components/upload-detail/incidents/BandFilter'
import { IncidentCard } from '@/components/upload-detail/incidents/IncidentCard'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { band } from '@/lib/confidence'
import type { Band } from '@/lib/types'

/**
 * What to look at first: incidents, most severe first, each with the findings behind it. The band
 * filter lives in the URL (?band=High) so a filtered view can be shared or reloaded.
 */
export function IncidentsTab({ uploadId }: { uploadId: string }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const selected = BANDS.find((b) => b === searchParams.get('band')) ?? null
  const incidents = useIncidents(uploadId)

  function selectBand(next: Band | null) {
    setSearchParams((params) => {
      if (next) params.set('band', next)
      else params.delete('band')
      return params
    })
  }

  if (incidents.isPending) return <p className="text-muted-foreground">Loading incidents…</p>
  if (incidents.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Couldn't load incidents: {incidents.error.message}</AlertDescription>
      </Alert>
    )
  }

  const counts = { High: 0, Medium: 0, Low: 0 }
  for (const incident of incidents.data) counts[band(incident.confidence)] += 1
  const shown = selected ? incidents.data.filter((incident) => band(incident.confidence) === selected) : incidents.data

  return (
    <div className="grid gap-4">
      <p className="max-w-3xl text-sm text-muted-foreground">
        An incident groups findings about the same user within 30 minutes of each other. Its confidence
        combines independent kinds of evidence, so agreeing detectors raise it; machine learning alone
        never reaches High. Severity is how bad it would be if real.
      </p>
      <BandFilter selected={selected} counts={counts} onChange={selectBand} />
      {shown.length === 0 ? (
        <p className="text-muted-foreground">
          {incidents.data.length === 0 ? 'Nothing suspicious was found in this log.' : `No ${selected} incidents.`}
        </p>
      ) : (
        <ul className="grid gap-4">
          {shown.map((incident) => (
            <li key={incident.id}>
              <IncidentCard incident={incident} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
