import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/firebase', () => ({ auth: {} }))
const uploadLog = vi.fn()
vi.mock('@/lib/upload', () => ({ uploadLog: (...args: unknown[]) => uploadLog(...args) }))

const { UploadCard, MAX_UPLOAD_BYTES } = await import('@/components/uploads/UploadCard')
const { ApiError } = await import('@/lib/api')

function renderCard() {
  const router = createMemoryRouter(
    [
      { path: '/uploads', element: <UploadCard /> },
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

const logFile = () => new File(['{"event":{}}'], 'log.ndjson')

describe('UploadCard', () => {
  it('shows progress, then "Analyzing…", then opens the new upload', async () => {
    let finish: (value: unknown) => void = () => {}
    uploadLog.mockImplementation((_file: File, onProgress: (f: number) => void) => {
      onProgress(0.4)
      return new Promise((resolve) => {
        finish = (value) => {
          onProgress(1)
          resolve(value)
        }
      })
    })
    const router = renderCard()

    await userEvent.upload(screen.getByLabelText('Log file'), logFile())
    expect(await screen.findByText('Uploading… 40%')).toBeInTheDocument()

    finish({ id: 'new-id' })
    expect(await screen.findByText('upload page')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/uploads/new-id')
  })

  it('links to the existing upload when the file is a duplicate', async () => {
    uploadLog.mockRejectedValue(
      new ApiError(409, 'duplicate_upload', 'You already uploaded this file.', { existing_upload_id: 'old-id' }),
    )
    renderCard()

    await userEvent.upload(screen.getByLabelText('Log file'), logFile())
    expect(await screen.findByText(/You already uploaded this file/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open it' })).toHaveAttribute('href', '/uploads/old-id')
  })

  it('rejects files over the size limit without uploading', async () => {
    uploadLog.mockReset()
    renderCard()
    const big = new File(['x'], 'big.log')
    Object.defineProperty(big, 'size', { value: MAX_UPLOAD_BYTES + 1 })

    await userEvent.upload(screen.getByLabelText('Log file'), big)
    expect(await screen.findByText(/over 25 MB/)).toBeInTheDocument()
    expect(uploadLog).not.toHaveBeenCalled()
  })

  it('offers the sample logs', () => {
    renderCard()
    for (const name of ['Full day', 'Small', 'Clean']) {
      expect(screen.getByRole('button', { name })).toBeEnabled()
    }
  })
})
