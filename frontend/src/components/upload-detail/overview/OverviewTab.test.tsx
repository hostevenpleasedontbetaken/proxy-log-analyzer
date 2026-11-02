import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { OverviewTab } from '@/components/upload-detail/overview/OverviewTab'
import type { TopList, UploadDetail, UploadStats } from '@/lib/types'

beforeAll(() => {
  // Recharts measures its container; jsdom has no layout, so give it a no-op observer.
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
})

const empty: TopList = { items: [], other: 0 }

function makeUpload(overrides: Partial<UploadStats> = {}): UploadDetail {
  const stats: UploadStats = {
    version: 1,
    totals: {
      requests: 2000,
      users: 5,
      client_ips: 5,
      devices: 6,
      hosts: 50,
      blocked: 30,
      threat_hits: 2,
      flagged: 100,
      high_risk: 1,
      bytes_out: 3 * 1024 * 1024,
      bytes_in: 0,
    },
    top: {
      users_by_requests: { items: [{ key: 'carla@acme.example', value: 900 }], other: 1100 },
      users_by_bytes_out: empty,
      hosts_by_requests: empty,
      hosts_by_bytes_out: empty,
      countries: empty,
      categories: empty,
      blocked_hosts: empty,
      block_reasons: empty,
      threats: empty,
    },
    breakdown: { action: {}, respcode_class: {}, urlclass: {} },
    timeline: {
      bucket_seconds: 900,
      buckets: [
        { t: '2026-10-20T00:00:00Z', allowed: 10, blocked: 1, threats: 0, flagged: 2, bytes_out: 2048 },
        { t: '2026-10-20T00:15:00Z', allowed: 12, blocked: 0, threats: 0, flagged: 0, bytes_out: 0 },
      ],
    },
    quality: { lines: 2001, parsed: 2000, errors: 1, warnings: { bad_ip: 3 } },
    detection: {
      incidents: 4,
      anomalies: 6,
      incidents_by_band: { High: 2, Medium: 1, Low: 1 },
      incidents_by_severity: {},
      ml: { ran: false, active_user_hours: 47, required_user_hours: 200 },
    },
    ...overrides,
  }
  return {
    id: 'u1',
    filename: 'log.ndjson',
    size_bytes: 1,
    status: 'ready',
    line_count: 2001,
    parsed_count: 2000,
    error_count: 1,
    time_start: '2026-10-20T00:00:00Z',
    time_end: '2026-10-20T00:29:00Z',
    created_at: '2026-11-02T12:00:00Z',
    parse_errors: [{ line: 7, reason: 'Not valid JSON', excerpt: '{"broken' }],
    stats,
    parser_version: '1',
    detector_version: '1',
    processed_at: '2026-11-02T12:00:01Z',
  }
}

function renderOverview(upload: UploadDetail) {
  render(
    <MemoryRouter initialEntries={['/uploads/u1']}>
      <OverviewTab upload={upload} />
    </MemoryRouter>,
  )
}

describe('OverviewTab', () => {
  it('links the Incidents tile, and each band, to the Incidents tab', () => {
    renderOverview(makeUpload())
    expect(screen.getByRole('link', { name: 'View incidents →' })).toHaveAttribute('href', '/uploads/u1?tab=incidents')
    expect(screen.getByRole('link', { name: '2 High' })).toHaveAttribute('href', '/uploads/u1?tab=incidents&band=High')
  })

  it('shows the headline numbers', () => {
    renderOverview(makeUpload())
    const summary = screen.getByRole('region', { name: 'Summary' })

    expect(within(summary).getByText('Incidents').nextSibling).toHaveTextContent('4')
    expect(within(summary).getAllByRole('listitem').map((item) => item.textContent)).toEqual(['2 High', '1 Medium', '1 Low'])
    expect(within(summary).getByText('5% of 2,000 entries')).toBeInTheDocument()
    expect(within(summary).getByText(/1.5% of requests · 2 threat hits/)).toBeInTheDocument()
  })

  it('explains when the Isolation Forest was skipped', () => {
    renderOverview(makeUpload())
    expect(screen.getByText(/Isolation Forest was skipped: it needs at least 200 .* this log has 47/)).toBeInTheDocument()
  })

  it('says when the Isolation Forest ran', () => {
    const ran = makeUpload()
    ran.stats!.detection.ml = { ran: true, active_user_hours: 407, required_user_hours: 200 }
    renderOverview(ran)
    expect(screen.getByText(/The model learned from 407 active user-hours/)).toBeInTheDocument()
  })

  it('switches the timeline to a table', async () => {
    renderOverview(makeUpload())
    await userEvent.click(screen.getByRole('button', { name: 'Show table' }))

    const rows = screen.getAllByRole('row')
    expect(rows).toHaveLength(3) // header + 2 buckets
    expect(within(rows[1]).getAllByRole('cell').map((cell) => cell.textContent)).toEqual(['00:00', '10', '1', '2', '2.0 KB'])
  })

  it('shows top lists with an "Other" total, and empty lists say so', () => {
    renderOverview(makeUpload())
    expect(screen.getByText('carla@acme.example')).toBeInTheDocument()
    expect(screen.getByText('1,100')).toBeInTheDocument()
    expect(screen.getAllByText('Nothing was blocked.')).toHaveLength(2)
    expect(screen.getByText('No known threats.')).toBeInTheDocument()
  })

  it('reports skipped lines and field warnings', async () => {
    renderOverview(makeUpload())
    expect(screen.getByText('2,000 of 2,001 lines parsed; 1 skipped.')).toBeInTheDocument()
    expect(screen.getByText('bad_ip: 3')).toBeInTheDocument()
    await userEvent.click(screen.getByText('First 1 skipped lines'))
    expect(screen.getByText('Not valid JSON')).toBeInTheDocument()
  })
})
