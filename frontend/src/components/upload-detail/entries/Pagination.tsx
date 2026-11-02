import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { formatCount } from '@/lib/format'

type Props = { page: number; pages: number; pageSize: number; total: number; onPage: (page: number) => void }

/** "1–100 of 2,018" with previous / next. */
export function Pagination({ page, pages, pageSize, total, onPage }: Props) {
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1
  const last = Math.min(page * pageSize, total)

  return (
    <nav aria-label="Pages" className="flex items-center justify-between gap-4 text-sm text-muted-foreground">
      <span className="tabular-nums">
        {formatCount(first)}–{formatCount(last)} of {formatCount(total)}
      </span>
      <div className="flex items-center gap-2">
        <span className="tabular-nums">
          Page {formatCount(page)} of {formatCount(pages)}
        </span>
        <Button variant="outline" size="icon-sm" aria-label="Previous page" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          <ChevronLeft />
        </Button>
        <Button variant="outline" size="icon-sm" aria-label="Next page" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          <ChevronRight />
        </Button>
      </div>
    </nav>
  )
}
