import { Sparkles } from 'lucide-react'
import { formatCount } from '@/lib/format'
import type { DetectionSummary } from '@/lib/types'

/** Whether the Isolation Forest ran on this upload, and if not, why. */
export function MlStatus({ ml }: { ml: DetectionSummary['ml'] }) {
  return (
    <p className="flex items-start gap-2 text-sm text-muted-foreground">
      <Sparkles className="mt-0.5 size-4 shrink-0" aria-hidden />
      {ml.ran ? (
        <span>
          Rules, statistics and an Isolation Forest (machine learning) analysed this log. The model learned
          from {formatCount(ml.active_user_hours)} active user-hours.
        </span>
      ) : (
        <span>
          Rules and statistics analysed this log. The Isolation Forest was skipped: it needs at least{' '}
          {formatCount(ml.required_user_hours)} active user-hours to learn what's normal, and this log has{' '}
          {formatCount(ml.active_user_hours)}.
        </span>
      )}
    </p>
  )
}
