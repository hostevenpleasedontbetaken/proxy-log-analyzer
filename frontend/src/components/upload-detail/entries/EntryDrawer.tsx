import { useQuery } from '@tanstack/react-query'
import { EntryFields } from '@/components/upload-detail/entries/EntryFields'
import { AnomalyItem } from '@/components/upload-detail/incidents/AnomalyItem'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { api } from '@/lib/api'
import { formatTimestamp } from '@/lib/format'
import type { EntryDetail } from '@/lib/types'

type Props = { uploadId: string; lineNo: number | null; onClose: () => void }

/** Side panel for one entry: why it was flagged (if it was), then every field. */
export function EntryDrawer({ uploadId, lineNo, onClose }: Props) {
  const entry = useQuery({
    queryKey: ['entry', uploadId, lineNo],
    queryFn: () => api<EntryDetail>(`/uploads/${uploadId}/entries/${lineNo}`),
    enabled: lineNo !== null,
    staleTime: Infinity,
  })

  return (
    <Sheet open={lineNo !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto data-[side=right]:sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>Log entry</SheetTitle>
          <SheetDescription>
            {entry.data ? `${entry.data.login ?? 'Unknown user'} · ${formatTimestamp(entry.data.ts)} UTC` : 'Loading…'}
          </SheetDescription>
        </SheetHeader>
        <div className="grid gap-6 px-4 pb-6">
          {entry.isError && (
            <Alert variant="destructive">
              <AlertDescription>Couldn't load this entry: {entry.error.message}</AlertDescription>
            </Alert>
          )}
          {entry.data && (
            <>
              <section className="grid gap-2">
                <h3 className="text-sm font-medium">Why flagged</h3>
                {entry.data.anomalies.length > 0 ? (
                  <ul className="grid gap-3 text-sm">
                    {entry.data.anomalies.map((anomaly) => (
                      <AnomalyItem key={anomaly.id} anomaly={anomaly} />
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">No detector flagged this entry.</p>
                )}
              </section>
              <EntryFields entry={entry.data} />
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
