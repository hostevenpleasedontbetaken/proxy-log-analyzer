import { CircleAlert, Info, TriangleAlert, type LucideIcon } from 'lucide-react'
import type { Band } from '@/lib/types'

/** Most to least confident, the order bands are listed in. */
export const BANDS: Band[] = ['High', 'Medium', 'Low']

// Icon + word + colour wherever a band is shown, so confidence never relies on colour alone.
export const BAND_STYLE: Record<Band, { icon: LucideIcon; color: string }> = {
  High: { icon: CircleAlert, color: 'var(--status-high)' },
  Medium: { icon: TriangleAlert, color: 'var(--status-medium)' },
  Low: { icon: Info, color: 'var(--muted-foreground)' },
}
