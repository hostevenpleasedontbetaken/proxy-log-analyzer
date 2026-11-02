import { formatBucket, formatBytes, formatCount } from '@/lib/format'
import type { TimelineBucket } from '@/lib/types'

type Props = {
  // Filled in by Recharts: the hovered bar's data point is in payload[0].payload.
  active?: boolean
  payload?: readonly { payload: TimelineBucket }[]
  bucketSeconds: number
  multiDay: boolean
}

/** Everything about one time bucket, shown on hover over either timeline chart. */
export function TimelineTooltip({ active, payload, bucketSeconds, multiDay }: Props) {
  const bucket = payload?.[0]?.payload
  if (!active || !bucket) return null
  const end = new Date(new Date(bucket.t).getTime() + bucketSeconds * 1000).toISOString()

  const rows: [string, string, string?][] = [
    ['Allowed', formatCount(bucket.allowed), 'var(--viz-allowed)'],
    ['Blocked', formatCount(bucket.blocked), 'var(--viz-blocked)'],
    ['Flagged', formatCount(bucket.flagged), 'var(--status-high)'],
    ['Threat hits', formatCount(bucket.threats)],
    ['Uploaded', formatBytes(bucket.bytes_out)],
  ]

  return (
    <div className="grid gap-1.5 rounded-lg border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      <p className="font-medium">
        {formatBucket(bucket.t, multiDay)} – {formatBucket(end, multiDay)} UTC
      </p>
      <dl className="grid grid-cols-[auto_auto] gap-x-4 gap-y-0.5">
        {rows.map(([label, value, color]) => (
          <div key={label} className="contents">
            <dt className="flex items-center gap-1.5 text-muted-foreground">
              <span className="size-2 rounded-sm" style={{ background: color ?? 'transparent' }} aria-hidden />
              {label}
            </dt>
            <dd className="text-right tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
