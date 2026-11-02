/**
 * The Entries tab's filters live in the URL (?tab=entries&user=…&page=2) so a view can be
 * reloaded, shared, or linked to from elsewhere (an incident, a timeline bar). These helpers turn
 * the URL into filters and the filters into the API's query string.
 */

export const PAGE_SIZE = 100

export type EntryFilters = {
  q?: string // text in the host or URL
  user?: string // exact login
  action?: 'Allowed' | 'Blocked'
  flagged?: boolean // only rows a finding covers
  band?: 'High' | 'Medium' // minimum confidence of those findings
  from?: string // ISO time, inclusive
  to?: string // ISO time, exclusive
  incident?: number
  anomaly?: number
  page: number
}

const MIN_CONFIDENCE = { High: 0.8, Medium: 0.5 } as const

/** Reads the filters from the page URL, ignoring anything malformed. */
export function readFilters(params: URLSearchParams): EntryFilters {
  const text = (key: string) => params.get(key)?.trim() || undefined
  const id = (key: string) => {
    const value = Number(params.get(key))
    return Number.isInteger(value) && value > 0 ? value : undefined
  }
  const action = params.get('action')
  const band = params.get('band')
  return {
    q: text('q'),
    user: text('user'),
    action: action === 'Allowed' || action === 'Blocked' ? action : undefined,
    flagged: params.get('flagged') === 'true' || undefined,
    band: band === 'High' || band === 'Medium' ? band : undefined,
    from: validTime(params.get('from')),
    to: validTime(params.get('to')),
    incident: id('incident'),
    anomaly: id('anomaly'),
    page: id('page') ?? 1,
  }
}

/** The query string for GET /uploads/<id>/entries. */
export function toApiQuery(filters: EntryFilters): string {
  const query = new URLSearchParams({ page: String(filters.page), page_size: String(PAGE_SIZE) })
  if (filters.q) query.set('q', filters.q)
  if (filters.user) query.set('user', filters.user)
  if (filters.action) query.set('action', filters.action)
  if (filters.flagged) query.set('flagged', 'true')
  if (filters.band) query.set('min_confidence', String(MIN_CONFIDENCE[filters.band]))
  if (filters.from) query.set('from', filters.from)
  if (filters.to) query.set('to', filters.to)
  if (filters.incident) query.set('incident_id', String(filters.incident))
  if (filters.anomaly) query.set('anomaly_id', String(filters.anomaly))
  return query.toString()
}

/** Writes changed filters into the URL. Any change closes the entry drawer; a filter change also goes back to page 1. */
export function writeFilters(params: URLSearchParams, changes: Partial<EntryFilters>): URLSearchParams {
  const next = new URLSearchParams(params)
  next.delete('entry')
  for (const [key, value] of Object.entries(changes)) {
    if (value === undefined || value === false || value === '') next.delete(key)
    else next.set(key, String(value))
  }
  if (!('page' in changes)) next.delete('page')
  if (next.get('page') === '1') next.delete('page')
  return next
}

/** True when anything narrows the table (used for "Clear filters" and empty-state wording). */
export function hasFilters(filters: EntryFilters): boolean {
  return Object.entries(filters).some(([key, value]) => key !== 'page' && value !== undefined)
}

function validTime(value: string | null): string | undefined {
  return value && !Number.isNaN(Date.parse(value)) ? value : undefined
}
