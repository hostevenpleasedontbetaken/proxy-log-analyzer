import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import type { EntryDetail, EntrySummary } from '@/lib/types'

vi.mock('@/lib/firebase', () => ({ auth: {} }))
const api = vi.fn()
vi.mock('@/lib/api', () => ({ api: (...args: unknown[]) => api(...args) }))

const { EntriesTab } = await import('@/components/upload-detail/entries/EntriesTab')

function entry(overrides: Partial<EntrySummary>): EntrySummary {
  return {
    line_no: 1,
    ts: '2026-10-20T11:21:17Z',
    login: 'umar@acme.example',
    dept: 'Sales',
    devicehostname: 'ACME-LT-0006',
    cltip: '10.20.1.16',
    host: 'dl.quickfiles-cdn.example',
    url: 'dl.quickfiles-cdn.example/invoice/8812/Invoice_8812.exe',
    reqmethod: 'GET',
    respcode: 403,
    action: 'Blocked',
    urlsubcat: 'Miscellaneous',
    reqsize: 685,
    respsize: 1800,
    riskscore: 95,
    threatname: 'Trojan.Win32.Emotet',
    anomaly_confidence: 0.95,
    max_severity: 4,
    ...overrides,
  }
}

const ROWS = [entry({ line_no: 7 }), entry({ line_no: 8, login: 'liam@acme.example', action: 'Allowed', respcode: 200, anomaly_confidence: null, url: 'crm.example/opportunities', host: 'crm.example' })]

const DETAIL = {
  ...ROWS[0],
  anomalies: [
    {
      id: 3,
      incident_id: 27,
      detector: 'rule',
      kind: 'known_threat',
      subject_type: 'user',
      subject: 'umar@acme.example',
      title: 'Known threat: Trojan.Win32.Emotet',
      explanation: 'Zscaler identified Trojan.Win32.Emotet in 2 requests.',
      confidence: 0.95,
      severity: 4,
      start_ts: '2026-10-20T11:21:17Z',
      end_ts: '2026-10-20T11:21:55Z',
      entry_count: 2,
      evidence: null,
    },
  ],
} as unknown as EntryDetail

function renderTab(url: string) {
  api.mockImplementation(async (path: string) => {
    if (/\/entries\/\d+$/.test(path)) return DETAIL
    return { entries: ROWS, page: 1, page_size: 100, total: 250, pages: 3 }
  })
  const router = createMemoryRouter([{ path: '/uploads/:id', element: <EntriesTab uploadId="u1" /> }], {
    initialEntries: [url],
  })
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

describe('EntriesTab', () => {
  it('requests the page and filters from the URL, and shows the rows', async () => {
    renderTab('/uploads/u1?tab=entries&flagged=true&incident=27&page=2')
    expect(await screen.findByText('liam@acme.example')).toBeInTheDocument()

    const [path] = api.mock.calls.at(-1) as [string]
    const query = new URLSearchParams(path.split('?')[1])
    expect(path.startsWith('/uploads/u1/entries?')).toBe(true)
    expect(Object.fromEntries(query)).toMatchObject({ page: '2', flagged: 'true', incident_id: '27' })
    expect(screen.getByText('1–100 of 250')).toBeInTheDocument()
  })

  it('marks flagged rows with their confidence', async () => {
    renderTab('/uploads/u1?tab=entries')
    const flaggedRow = (await screen.findByText('umar@acme.example')).closest('tr')!
    expect(within(flaggedRow).getByText('High 95%')).toBeInTheDocument()
    const plainRow = screen.getByText('liam@acme.example').closest('tr')!
    expect(within(plainRow).queryByText(/%/)).not.toBeInTheDocument()
  })

  it('pages forward, keeping the filters', async () => {
    const router = renderTab('/uploads/u1?tab=entries&action=Blocked')
    await userEvent.click(await screen.findByRole('button', { name: 'Next page' }))
    expect(router.state.location.search).toBe('?tab=entries&action=Blocked&page=2')
  })

  it('applies "Flagged only" and goes back to page 1', async () => {
    const router = renderTab('/uploads/u1?tab=entries&page=3')
    await userEvent.click(await screen.findByRole('checkbox', { name: 'Flagged only' }))
    expect(router.state.location.search).toBe('?tab=entries&flagged=true')
  })

  it('opens a row in the drawer with why it was flagged, and closes it', async () => {
    const router = renderTab('/uploads/u1?tab=entries')
    await userEvent.click(await screen.findByText('umar@acme.example'))
    expect(router.state.location.search).toBe('?tab=entries&entry=7')

    const drawer = await screen.findByRole('dialog')
    expect(await within(drawer).findByText('Known threat: Trojan.Win32.Emotet')).toBeInTheDocument()
    expect(within(drawer).getByText('Sales')).toBeInTheDocument() // a field from the grouped details

    await userEvent.keyboard('{Escape}')
    expect(router.state.location.search).toBe('?tab=entries')
  })

  it('shows link filters as removable chips, and clears everything', async () => {
    const router = renderTab('/uploads/u1?tab=entries&from=2026-10-20T14:30:00Z&to=2026-10-20T14:45:00Z&incident=27&user=a@b.example')
    await userEvent.click(await screen.findByRole('button', { name: /Remove filter: Oct 20, 14:30 – 14:45 UTC/ }))
    expect(router.state.location.search).toBe('?tab=entries&incident=27&user=a%40b.example')

    expect(screen.getByText('Incident: #27')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(router.state.location.search).toBe('?tab=entries')
  })
})
