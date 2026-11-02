import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatCount } from '@/lib/format'
import type { TopList } from '@/lib/types'

type Props = {
  title: string
  list: TopList
  /** How to show each value (counts by default; bytes for upload volume). */
  format?: (value: number) => string
  emptyText?: string
}

/** A ranked top-10 with a bar per row scaled to the largest, and the rest summed as "Other". */
export function TopListCard({ title, list, format = formatCount, emptyText = 'None' }: Props) {
  const max = Math.max(1, ...list.items.map((item) => item.value))

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {list.items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{emptyText}</p>
        ) : (
          <ol className="grid gap-1.5 text-sm">
            {list.items.map((item) => (
              <li key={item.key} className="grid gap-0.5">
                <div className="flex justify-between gap-3">
                  <span className="truncate" title={item.key}>
                    {item.key}
                  </span>
                  <span className="shrink-0 text-muted-foreground tabular-nums">{format(item.value)}</span>
                </div>
                <div
                  className="h-1 rounded-full bg-[var(--viz-allowed)] opacity-60"
                  style={{ width: `${(item.value / max) * 100}%` }}
                  aria-hidden
                />
              </li>
            ))}
            {list.other > 0 && (
              <li className="flex justify-between gap-3 pt-1 text-muted-foreground">
                <span>Other</span>
                <span className="tabular-nums">{format(list.other)}</span>
              </li>
            )}
          </ol>
        )}
      </CardContent>
    </Card>
  )
}
