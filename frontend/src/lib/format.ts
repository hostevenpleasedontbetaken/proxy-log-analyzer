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

/** part of whole as a percentage: 2018 of 18654 → "10.8%"; tiny shares show as "<0.1%". */
export function formatPercent(part: number, whole: number): string {
  if (!whole) return '—'
  const percent = (part / whole) * 100
  if (percent > 0 && percent < 0.1) return '<0.1%'
  return `${Math.round(percent * 10) / 10}%`
}

/** Short axis/tooltip label for a timeline bucket: "14:15", or "Oct 21 14:00" for multi-day logs. */
export function formatBucket(iso: string, multiDay: boolean): string {
  return (multiDay ? dateTime : timeOnly).format(new Date(iso))
}

/** A timeline bucket's length in words: 60 → "minute", 900 → "15 minutes", 3600 → "hour". */
export function formatBucketSize(seconds: number): string {
  let amount = seconds / 60
  let unit = 'minute'
  if (seconds % 86400 === 0) {
    amount = seconds / 86400
    unit = 'day'
  } else if (seconds % 3600 === 0) {
    amount = seconds / 3600
    unit = 'hour'
  }
  return amount === 1 ? unit : `${amount} ${unit}s`
}

const compact = new Intl.NumberFormat('en-US', { notation: 'compact' })

/** Axis ticks: 1500 → "1.5K". */
export function formatCompact(n: number): string {
  return compact.format(n)
}

const timestamp = new Intl.DateTimeFormat('en-US', {
  timeZone: 'UTC',
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hourCycle: 'h23',
})

/** One log entry's time, to the second: "Oct 20, 14:32:28" (UTC). */
export function formatTimestamp(iso: string): string {
  return timestamp.format(new Date(iso))
}
