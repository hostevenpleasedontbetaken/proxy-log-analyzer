import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Incident } from '@/lib/types'

/**
 * An upload's incidents, each with its findings. Shared by the Incidents tab and the Entries
 * filter chips (which only need it to show a name), so it's fetched once per upload.
 */
export function useIncidents(uploadId: string, { enabled = true } = {}) {
  return useQuery({
    queryKey: ['incidents', uploadId],
    queryFn: () => api<{ incidents: Incident[] }>(`/uploads/${uploadId}/incidents`),
    select: (data) => data.incidents,
    staleTime: Infinity, // an analysis never changes once stored
    enabled,
  })
}
