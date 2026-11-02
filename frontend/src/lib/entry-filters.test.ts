import { describe, expect, it } from 'vitest'
import { hasFilters, readFilters, toApiQuery, writeFilters } from '@/lib/entry-filters'

const params = (query: string) => new URLSearchParams(query)

describe('readFilters', () => {
  it('reads every filter from the URL', () => {
    expect(
      readFilters(params('tab=entries&q=dropbin&user=a@b.example&action=Blocked&flagged=true&band=High&from=2026-10-20T14:30:00Z&to=2026-10-20T14:45:00Z&incident=25&anomaly=7&page=3')),
    ).toEqual({
      q: 'dropbin',
      user: 'a@b.example',
      action: 'Blocked',
      flagged: true,
      band: 'High',
      from: '2026-10-20T14:30:00Z',
      to: '2026-10-20T14:45:00Z',
      incident: 25,
      anomaly: 7,
      page: 3,
    })
  })

  it('ignores malformed values instead of sending them to the API', () => {
    expect(readFilters(params('action=Maybe&band=Ultra&from=yesterday&incident=abc&page=-2&q=%20%20'))).toEqual({
      q: undefined,
      user: undefined,
      action: undefined,
      flagged: undefined,
      band: undefined,
      from: undefined,
      to: undefined,
      incident: undefined,
      anomaly: undefined,
      page: 1,
    })
  })
})

describe('toApiQuery', () => {
  it('maps the filters to the API parameters', () => {
    const query = params(toApiQuery(readFilters(params('band=Medium&incident=25&anomaly=7&page=2'))))
    expect(Object.fromEntries(query)).toEqual({
      page: '2',
      page_size: '100',
      min_confidence: '0.5',
      incident_id: '25',
      anomaly_id: '7',
    })
  })
})

describe('writeFilters', () => {
  it('sets and clears filters, keeps the tab, goes back to page 1 and closes the drawer', () => {
    const next = writeFilters(params('tab=entries&user=a@b.example&page=4&entry=12'), { action: 'Blocked', user: undefined })
    expect(next.toString()).toBe('tab=entries&action=Blocked')
  })

  it('changes the page without touching filters', () => {
    expect(writeFilters(params('tab=entries&flagged=true'), { page: 2 }).toString()).toBe('tab=entries&flagged=true&page=2')
    expect(writeFilters(params('tab=entries&page=2'), { page: 1 }).toString()).toBe('tab=entries')
  })
})

describe('hasFilters', () => {
  it('ignores the page', () => {
    expect(hasFilters(readFilters(params('page=3')))).toBe(false)
    expect(hasFilters(readFilters(params('flagged=true')))).toBe(true)
  })
})
