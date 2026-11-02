import type { ReactNode } from 'react'
import { Link, type To } from 'react-router'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'

type Props = {
  label: string
  value: string
  children?: ReactNode
  /** Makes the whole tile open this page, e.g. the tab with the detail behind the number. */
  link?: { to: To; label: string }
}

/**
 * One headline number with a label above and context below. With `link`, the tile is clickable:
 * the link's hit area is stretched over the whole card (a link can't wrap other links), and any
 * links inside `children` sit above it with `relative z-10`.
 */
export function StatTile({ label, value, children, link }: Props) {
  return (
    <Card className={cn(link && 'relative transition-colors hover:bg-muted/50')}>
      <CardContent className="grid gap-1">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-3xl font-semibold tabular-nums">{value}</p>
        {children && <div className="text-sm text-muted-foreground">{children}</div>}
        {link && (
          <Link
            to={link.to}
            className="mt-1 w-fit text-sm font-medium after:absolute after:inset-0 after:rounded-xl hover:underline focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring"
          >
            {link.label} →
          </Link>
        )}
      </CardContent>
    </Card>
  )
}
