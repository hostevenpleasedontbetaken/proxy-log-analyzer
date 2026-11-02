import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import type { UploadDetail } from '@/lib/types'

// The tabs' contents have their own tests; here only which one is shown matters.
vi.mock('@/components/upload-detail/overview/OverviewTab', () => ({ OverviewTab: () => <p>overview content</p> }))
vi.mock('@/components/upload-detail/incidents/IncidentsTab', () => ({ IncidentsTab: () => <p>incidents content</p> }))

const { UploadTabs } = await import('@/components/upload-detail/UploadTabs')

const upload = { id: 'u1', stats: { detection: { incidents: 12 } } } as unknown as UploadDetail

function renderTabs(url: string) {
  const router = createMemoryRouter([{ path: '/uploads/:id', element: <UploadTabs upload={upload} /> }], {
    initialEntries: [url],
  })
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

describe('UploadTabs', () => {
  it('shows the Overview by default, with the incident count on the Incidents tab', () => {
    renderTabs('/uploads/u1')
    expect(screen.getByText('overview content')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Incidents(12)' })).toBeInTheDocument()
  })

  it('opens the tab named in the URL', () => {
    renderTabs('/uploads/u1?tab=incidents')
    expect(screen.getByText('incidents content')).toBeInTheDocument()
  })

  it('falls back to the Overview for an unknown tab', () => {
    renderTabs('/uploads/u1?tab=nope')
    expect(screen.getByText('overview content')).toBeInTheDocument()
  })

  it('puts the tab in the URL and drops the other tab’s filters', async () => {
    const router = renderTabs('/uploads/u1?tab=incidents&band=High')
    await userEvent.click(screen.getByRole('tab', { name: 'Overview' }))
    expect(router.state.location.search).toBe('')

    await userEvent.click(screen.getByRole('tab', { name: /Incidents/ }))
    expect(router.state.location.search).toBe('?tab=incidents')
  })
})
