import { DataQuality } from '@/components/upload-detail/overview/DataQuality'
import { IncidentBands } from '@/components/upload-detail/overview/IncidentBands'
import { MlStatus } from '@/components/upload-detail/overview/MlStatus'
import { StatTile } from '@/components/upload-detail/overview/StatTile'
import { Timeline } from '@/components/upload-detail/overview/Timeline'
import { TopListCard } from '@/components/upload-detail/overview/TopListCard'
import { formatBytes, formatCount, formatPercent } from '@/lib/format'
import type { UploadDetail } from '@/lib/types'

/** The SOC summary for one upload: headline numbers, activity over time, and who/what stands out. */
export function OverviewTab({ upload }: { upload: UploadDetail }) {
  const stats = upload.stats
  if (!stats) return <p className="text-muted-foreground">This upload has no analysis stored.</p>
  const { totals, detection, top } = stats

  return (
    <div className="grid gap-6">
      <section aria-label="Summary" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Incidents"
          value={formatCount(detection.incidents)}
          link={{ to: { search: '?tab=incidents' }, label: 'View incidents' }}
        >
          <IncidentBands counts={detection.incidents_by_band} />
        </StatTile>
        <StatTile
          label="Flagged entries"
          value={formatCount(totals.flagged)}
          link={{ to: { search: '?tab=entries&flagged=true' }, label: 'View flagged entries' }}
        >
          {formatPercent(totals.flagged, totals.requests)} of {formatCount(totals.requests)} entries
        </StatTile>
        <StatTile label="Blocked requests" value={formatCount(totals.blocked)}>
          {formatPercent(totals.blocked, totals.requests)} of requests · {formatCount(totals.threat_hits)} threat hits
        </StatTile>
        <StatTile label="Users" value={formatCount(totals.users)}>
          {formatCount(totals.devices)} devices · {formatCount(totals.hosts)} hosts · {formatBytes(totals.bytes_out)}{' '}
          uploaded
        </StatTile>
      </section>

      <MlStatus ml={detection.ml} />

      <Timeline timeline={stats.timeline} />

      <section aria-label="Top lists" className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <TopListCard title="Most active users" list={top.users_by_requests} />
        <TopListCard title="Most data uploaded, by user" list={top.users_by_bytes_out} format={formatBytes} />
        <TopListCard title="Most requested hosts" list={top.hosts_by_requests} />
        <TopListCard title="Most blocked hosts" list={top.blocked_hosts} emptyText="Nothing was blocked." />
        <TopListCard title="Block reasons" list={top.block_reasons} emptyText="Nothing was blocked." />
        <TopListCard title="Threats Zscaler named" list={top.threats} emptyText="No known threats." />
      </section>

      <DataQuality quality={stats.quality} parseErrors={upload.parse_errors} />
    </div>
  )
}
