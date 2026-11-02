import { BAND_STYLE } from '@/components/upload-detail/band-style'
import { band, formatConfidence } from '@/lib/confidence'

/** "High 95%" with the band's icon and colour. */
export function ConfidenceBadge({ confidence }: { confidence: number }) {
  const level = band(confidence)
  const { icon: Icon, color } = BAND_STYLE[level]
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-md border px-1.5 py-0.5 text-xs font-medium whitespace-nowrap">
      <Icon className="size-3.5" style={{ color }} aria-hidden />
      {level} {formatConfidence(confidence)}
    </span>
  )
}
