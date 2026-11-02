/** Display helpers. Times are shown in UTC, the time zone the logs are recorded in. */

const UNITS = ['B', 'KB', 'MB', 'GB']

/** 1536 → "1.5 KB"; 25 * 1024 * 1024 → "25 MB". */
export function formatBytes(bytes: number): string {
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024
    unit += 1
  }
  const digits = unit === 0 || value >= 10 ? 0 : 1
  return `${value.toFixed(digits)} ${UNITS[unit]}`
}

/** 12345 → "12,345". */
export function formatCount(n: number): string {
  return n.toLocaleString('en-US')
}

const dateTime = new Intl.DateTimeFormat('en-US', {
  timeZone: 'UTC',
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})
const timeOnly = new Intl.DateTimeFormat('en-US', {
  timeZone: 'UTC',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

/** "Oct 14, 00:00 – 23:59 UTC", or with both dates when the range spans days. */
export function formatTimeRange(start: string | null, end: string | null): string {
  if (!start || !end) return '—'
  const from = new Date(start)
  const to = new Date(end)
  const sameDay = from.toISOString().slice(0, 10) === to.toISOString().slice(0, 10)
  return `${dateTime.format(from)} – ${(sameDay ? timeOnly : dateTime).format(to)} UTC`
}

/** "Nov 2, 14:05 UTC". */
export function formatDateTime(iso: string): string {
  return `${dateTime.format(new Date(iso))} UTC`
}
