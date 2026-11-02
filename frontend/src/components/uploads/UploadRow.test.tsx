import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import type { UploadSummary } from '@/lib/types'

vi.mock('@/lib/firebase', () => ({ auth: {} }))
const { UploadRow } = await import('@/components/uploads/UploadRow')

const upload: UploadSummary = {
  id: 'u1',
  filename: 'acme-web-day.ndjson.gz',
  size_bytes: 1031814,
  status: 'ready',
  line_count: 18654,
  parsed_count: 18654,
  error_count: 0,
  time_start: '2026-10-20T00:00:00Z',
  time_end: '2026-10-20T23:59:00Z',
  created_at: '2026-11-02T20:36:00Z',
}

function renderRow() {
  const router = createMemoryRouter(
    [
      {
        path: '/uploads',
        element: (
          <table>
            <tbody>
              <UploadRow upload={upload} />
            </tbody>
          </table>
        ),
      },
      { path: '/uploads/:id', element: <p>upload page</p> },
    ],
    { initialEntries: ['/uploads'] },
  )
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

describe('UploadRow', () => {
  it('opens the upload when any part of the row is clicked', async () => {
    const router = renderRow()
    await userEvent.click(screen.getByText('18,654'))
    expect(router.state.location.pathname).toBe('/uploads/u1')
  })

  it('opens the delete dialog without navigating, and cancelling stays on the list', async () => {
    const router = renderRow()
    await userEvent.click(screen.getByRole('button', { name: 'Delete acme-web-day.ndjson.gz' }))
    expect(await screen.findByRole('alertdialog')).toBeInTheDocument()

    // A click on the dialog's text bubbles to the row in React; it must not open the upload.
    await userEvent.click(screen.getByText(/It can't be undone/))
    expect(router.state.location.pathname).toBe('/uploads')

    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(router.state.location.pathname).toBe('/uploads')
  })
})
