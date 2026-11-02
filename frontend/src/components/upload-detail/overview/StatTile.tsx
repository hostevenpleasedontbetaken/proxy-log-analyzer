import type { ReactNode } from 'react'
import { Card, CardContent } from '@/components/ui/card'

/** One headline number with a label above and context below. */
export function StatTile({ label, value, children }: { label: string; value: string; children?: ReactNode }) {
  return (
    <Card>
      <CardContent className="grid gap-1">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-3xl font-semibold tabular-nums">{value}</p>
        {children && <div className="text-sm text-muted-foreground">{children}</div>}
      </CardContent>
    </Card>
  )
}
