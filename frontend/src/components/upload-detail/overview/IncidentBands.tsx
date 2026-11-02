import { Link } from 'react-router'
import { BAND_STYLE, BANDS } from '@/components/upload-detail/band-style'
import type { Band } from '@/lib/types'

/** "7 High · 1 Medium · 4 Low": incidents by confidence band, each linking to that filter. */
export function IncidentBands({ counts }: { counts: Record<Band, number> }) {
  return (
    <ul className="flex flex-wrap gap-x-3 gap-y-1">
      {BANDS.map((band) => {
        const { icon: Icon, color } = BAND_STYLE[band]
        return (
          <li key={band}>
            {/* relative z-10: above the tile's stretched "View incidents" link. */}
            <Link
              to={{ search: `?tab=incidents&band=${band}` }}
              className="relative z-10 flex items-center gap-1 rounded-sm hover:text-foreground hover:underline"
            >
              <Icon className="size-4" style={{ color }} aria-hidden />
              <span className="font-medium text-foreground tabular-nums">{counts[band]}</span> {band}
            </Link>
          </li>
        )
      })}
    </ul>
  )
}
