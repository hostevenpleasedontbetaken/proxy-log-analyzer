import { BAND_STYLE, BANDS } from '@/components/upload-detail/band-style'
import { Button } from '@/components/ui/button'
import type { Band } from '@/lib/types'

type Props = {
  selected: Band | null // null = all
  counts: Record<Band, number>
  onChange: (band: Band | null) => void
}

/** "All 12 · High 7 · Medium 1 · Low 4" toggle buttons. */
export function BandFilter({ selected, counts, onChange }: Props) {
  const total = BANDS.reduce((sum, band) => sum + counts[band], 0)

  return (
    <div role="group" aria-label="Filter by confidence" className="flex flex-wrap gap-2">
      <Button size="sm" variant={selected === null ? 'default' : 'outline'} aria-pressed={selected === null} onClick={() => onChange(null)}>
        All <span className="tabular-nums">{total}</span>
      </Button>
      {BANDS.map((band) => {
        const { icon: Icon, color } = BAND_STYLE[band]
        const active = selected === band
        return (
          <Button key={band} size="sm" variant={active ? 'default' : 'outline'} aria-pressed={active} onClick={() => onChange(band)}>
            <Icon style={active ? undefined : { color }} aria-hidden />
            {band} <span className="tabular-nums">{counts[band]}</span>
          </Button>
        )
      })}
    </div>
  )
}
