import { describe, expect, it } from 'vitest'
import { formatBytes, formatCount, formatDateTime, formatTimeRange } from '@/lib/format'

describe('formatBytes', () => {
  it.each([
    [0, '0 B'],
    [1023, '1023 B'],
    [1536, '1.5 KB'],
    [1031814, '1008 KB'],
    [25 * 1024 * 1024, '25 MB'],
    [5.5 * 1024 ** 3, '5.5 GB'],
  ])('%d → %s', (bytes, expected) => {
    expect(formatBytes(bytes)).toBe(expected)
  })
})

describe('formatCount', () => {
  it('adds thousands separators', () => {
    expect(formatCount(18654)).toBe('18,654')
  })
})

describe('formatTimeRange', () => {
  it('shows the date once for a same-day range, in UTC', () => {
    expect(formatTimeRange('2026-10-20T00:00:05Z', '2026-10-20T23:59:58Z')).toBe('Oct 20, 00:00 – 23:59 UTC')
  })

  it('shows both dates when the range spans days', () => {
    expect(formatTimeRange('2026-10-20T22:00:00Z', '2026-10-21T02:30:00Z')).toBe('Oct 20, 22:00 – Oct 21, 02:30 UTC')
  })

  it('handles a missing range', () => {
    expect(formatTimeRange(null, null)).toBe('—')
  })
})

describe('formatDateTime', () => {
  it('formats in UTC', () => {
    expect(formatDateTime('2026-11-02T14:05:00+00:00')).toBe('Nov 2, 14:05 UTC')
  })
})
