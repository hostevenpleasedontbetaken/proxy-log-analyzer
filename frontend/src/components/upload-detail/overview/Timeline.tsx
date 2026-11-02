import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { LegendItem } from '@/components/upload-detail/overview/LegendItem'
import { TimelineTable } from '@/components/upload-detail/overview/TimelineTable'
import { TimelineTooltip } from '@/components/upload-detail/overview/TimelineTooltip'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatBucket, formatBucketSize, formatCompact } from '@/lib/format'
import type { UploadStats } from '@/lib/types'

// Both charts share this so their bars line up under each other.
const Y_AXIS_WIDTH = 40
const AXIS_TICK = { fontSize: 12, fill: 'var(--muted-foreground)' }
const NO_ANIMATION = { isAnimationActive: false } as const

/**
 * Requests over time (allowed + blocked, stacked) and, on its own scale below, how many entries
 * detection flagged. Two charts instead of one with two y-axes: flagged counts are a subset of
 * requests and far smaller, so sharing an axis would flatten them. Hovering either chart shows the
 * same bucket in both (shared `syncId`).
 */
export function Timeline({ timeline }: { timeline: UploadStats['timeline'] }) {
  const [showTable, setShowTable] = useState(false)
  const { buckets, bucket_seconds: bucketSeconds } = timeline
  const multiDay = buckets.length > 0 && buckets[0].t.slice(0, 10) !== buckets[buckets.length - 1].t.slice(0, 10)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Activity over time</CardTitle>
        <CardDescription>Requests per {formatBucketSize(bucketSeconds)}, UTC. Hover a bar for details.</CardDescription>
        <CardAction>
          <Button variant="outline" size="sm" onClick={() => setShowTable((shown) => !shown)}>
            {showTable ? 'Show chart' : 'Show table'}
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {showTable ? (
          <TimelineTable buckets={buckets} multiDay={multiDay} />
        ) : (
          <div className="grid gap-2">
            <ul className="flex gap-4 text-sm text-muted-foreground">
              <LegendItem color="var(--viz-allowed)" label="Allowed" />
              <LegendItem color="var(--viz-blocked)" label="Blocked" />
            </ul>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={buckets} syncId="timeline" barCategoryGap={1} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--border)" />
                <XAxis dataKey="t" hide />
                <YAxis width={Y_AXIS_WIDTH} tickFormatter={formatCompact} allowDecimals={false} axisLine={false} tickLine={false} tick={AXIS_TICK} />
                <Tooltip
                  content={<TimelineTooltip bucketSeconds={bucketSeconds} multiDay={multiDay} />}
                  cursor={{ fill: 'var(--muted)' }}
                  {...NO_ANIMATION}
                />
                <Bar dataKey="allowed" stackId="requests" fill="var(--viz-allowed)" {...NO_ANIMATION} />
                <Bar dataKey="blocked" stackId="requests" fill="var(--viz-blocked)" radius={[2, 2, 0, 0]} {...NO_ANIMATION} />
              </BarChart>
            </ResponsiveContainer>

            <p className="mt-2 text-sm text-muted-foreground">Flagged entries</p>
            <ResponsiveContainer width="100%" height={100}>
              <BarChart data={buckets} syncId="timeline" barCategoryGap={1} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--border)" />
                <XAxis
                  dataKey="t"
                  tickFormatter={(t: string) => formatBucket(t, multiDay)}
                  minTickGap={32}
                  axisLine={false}
                  tickLine={false}
                  tick={AXIS_TICK}
                />
                <YAxis width={Y_AXIS_WIDTH} tickFormatter={formatCompact} allowDecimals={false} axisLine={false} tickLine={false} tick={AXIS_TICK} />
                {/* The details appear in the chart above; this one only highlights the hovered bucket. */}
                <Tooltip content={() => null} cursor={{ fill: 'var(--muted)' }} {...NO_ANIMATION} />
                <Bar dataKey="flagged" fill="var(--status-high)" radius={[2, 2, 0, 0]} {...NO_ANIMATION} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
