import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { EntriesTable } from '@/components/upload-detail/entries/EntriesTable'
import { EntryDrawer } from '@/components/upload-detail/entries/EntryDrawer'
import { EntryFilterBar } from '@/components/upload-detail/entries/EntryFilterBar'
import { FilterChips } from '@/components/upload-detail/entries/FilterChips'
import { Pagination } from '@/components/upload-detail/entries/Pagination'
import { useIncidents } from '@/components/upload-detail/useIncidents'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent } from '@/components/ui/card'
import { api } from '@/lib/api'
import { hasFilters, readFilters, toApiQuery, writeFilters, type EntryFilters } from '@/lib/entry-filters'
import type { EntriesPage } from '@/lib/types'

/**
 * The evidence: every log entry, 100 per page, filterable, with flagged rows highlighted. Filters,
 * page and the open entry (?entry=<line>) are all in the URL, so other tabs can link straight
 * to "this incident's entries" or "this 15 minutes".
 */
export function EntriesTab({ uploadId }: { uploadId: string }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = readFilters(searchParams)
  const apiQuery = toApiQuery(filters)
  const openLine = Number(searchParams.get('entry')) || null

  const page = useQuery({
    queryKey: ['entries', uploadId, apiQuery],
    queryFn: () => api<EntriesPage>(`/uploads/${uploadId}/entries?${apiQuery}`),
    staleTime: Infinity,
    // Keep showing the current page while the next one loads, instead of flashing empty.
    placeholderData: keepPreviousData,
  })
  // Only to name an incident/finding filter chip; cached if the Incidents tab was opened first.
  const incidents = useIncidents(uploadId, { enabled: Boolean(filters.incident || filters.anomaly) })

  function update(changes: Partial<EntryFilters>) {
    setSearchParams((params) => writeFilters(params, changes))
  }

  function setOpenLine(lineNo: number | null) {
    setSearchParams((params) => {
      if (lineNo === null) params.delete('entry')
      else params.set('entry', String(lineNo))
      return params
    })
  }

  return (
    <div className="grid gap-4">
      <EntryFilterBar filters={filters} onChange={update} />
      {hasFilters(filters) && (
        <FilterChips filters={filters} incidents={incidents.data} onChange={update} onClearAll={() => setSearchParams({ tab: 'entries' })} />
      )}

      {page.isError && (
        <Alert variant="destructive">
          <AlertDescription>Couldn't load entries: {page.error.message}</AlertDescription>
        </Alert>
      )}
      {page.isPending && <p className="text-muted-foreground">Loading entries…</p>}
      {page.data && (
        <Card size="sm" className={page.isPlaceholderData ? 'opacity-60 transition-opacity' : undefined}>
          <CardContent className="grid gap-3">
            {page.data.total === 0 ? (
              <p className="py-8 text-center text-muted-foreground">No entries match these filters.</p>
            ) : (
              <>
                <EntriesTable entries={page.data.entries} selectedLine={openLine} onOpen={setOpenLine} />
                <Pagination
                  page={page.data.page}
                  pages={page.data.pages}
                  pageSize={page.data.page_size}
                  total={page.data.total}
                  onPage={(next) => update({ page: next })}
                />
              </>
            )}
          </CardContent>
        </Card>
      )}

      <EntryDrawer uploadId={uploadId} lineNo={openLine} onClose={() => setOpenLine(null)} />
    </div>
  )
}
