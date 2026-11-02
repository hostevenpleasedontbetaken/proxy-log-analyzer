import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import type { Anomaly, Incident } from '@/lib/types'

vi.mock('@/lib/firebase', () => ({ auth: {} }))
const api = vi.fn()
vi.mock('@/lib/api', () => ({ api: (...args: unknown[]) => api(...args) }))

const { IncidentsTab } = await import('@/components/upload-detail/incidents/IncidentsTab')

function anomaly(overrides: Partial<Anomaly>): Anomaly {
  return {
    id: 1,
    incident_id: 1,
    detector: 'rule',
    kind: 'known_threat',
    subject_type: 'user',
    subject: 'umar@acme.example',
    title: 'Known threat',
    explanation: 'Zscaler identified a trojan.',
    confidence: 0.95,
    severity: 4,
    start_ts: '2026-10-20T11:21:00Z',
    end_ts: '2026-10-20T11:22:00Z',
    entry_count: 2,
    evidence: null,
    ...overrides,
  }
}

function incident(overrides: Partial<Incident>): Incident {
  return {
    id: 1,
    subject_type: 'user',
    subject: 'umar@acme.example',
    title: 'Known threat',
    summary: null,
    severity: 4,
    confidence: 0.95,
    start_ts: '2026-10-20T11:21:00Z',
    end_ts: '2026-10-20T11:22:00Z',
    anomalies: [anomaly({})],
    ...overrides,
  }
}

const INCIDENTS = [
  incident({
    id: 1,
    anomalies: [
      anomaly({ id: 2, detector: 'statistical', title: 'High-risk destination', confidence: 0.82 }),
      anomaly({ id: 1, title: 'Known threat', confidence: 0.95 }),
    ],
  }),
  incident({ id: 2, title: 'Unusual hour of activity', subject: 'vera@acme.example', confidence: 0.6, severity: 2, anomalies: [anomaly({ id: 3, detector: 'ml', title: 'Unusual hour', confidence: 0.6, entry_count: 1 })] }),
  incident({ id: 3, title: 'Browsing outside usual hours', confidence: 0.45, severity: 1 }),
]

function renderTab(url = '/uploads/u1?tab=incidents', incidents = INCIDENTS) {
  api.mockResolvedValue({ incidents })
  const router = createMemoryRouter([{ path: '/uploads/:id', element: <IncidentsTab uploadId="u1" /> }], {
    initialEntries: [url],
  })
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

describe('IncidentsTab', () => {
  it('lists incidents with confidence, severity and evidence strongest first', async () => {
    renderTab()
    const card = await screen.findByRole('article', { name: 'Known threat' })

    expect(api).toHaveBeenCalledWith('/uploads/u1/incidents')
    expect(within(card).getByText('High 95%')).toBeInTheDocument()
    expect(within(card).getByText('Critical severity')).toBeInTheDocument()
    expect(within(card).getByText('Why it was flagged (2 findings)')).toBeInTheDocument()
    const evidence = within(within(card).getByRole('list', { name: 'Evidence' })).getAllByRole('listitem')
    expect(evidence.map((item) => item.textContent)).toEqual([
      expect.stringContaining('Known threat'),
      expect.stringContaining('High-risk destination'),
    ])
  })

  it('names the kind of detector, and links to the entries of each finding and incident', async () => {
    renderTab()
    expect(await screen.findByText('Machine learning')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '1 entry' })).toHaveAttribute('href', '/uploads/u1?tab=entries&anomaly=3')
    const card = screen.getByRole('article', { name: 'Unusual hour of activity' })
    expect(within(card).getByRole('link', { name: "View this incident's entries →" })).toHaveAttribute(
      'href',
      '/uploads/u1?tab=entries&incident=2',
    )
  })

  it('filters by confidence band, keeping the choice in the URL', async () => {
    const router = renderTab()
    await userEvent.click(await screen.findByRole('button', { name: /Medium/ }))

    expect(router.state.location.search).toBe('?tab=incidents&band=Medium')
    expect(screen.getByText('Unusual hour of activity')).toBeInTheDocument()
    expect(screen.queryByText('Browsing outside usual hours')).not.toBeInTheDocument()
  })

  it('opens already filtered when the URL has a band', async () => {
    renderTab('/uploads/u1?tab=incidents&band=Low')
    expect(await screen.findByText('Browsing outside usual hours')).toBeInTheDocument()
    expect(screen.queryByText('Unusual hour of activity')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Low/ })).toHaveAttribute('aria-pressed', 'true')
  })

  it('says when nothing was found', async () => {
    renderTab('/uploads/u1?tab=incidents', [])
    expect(await screen.findByText('Nothing suspicious was found in this log.')).toBeInTheDocument()
  })
})
