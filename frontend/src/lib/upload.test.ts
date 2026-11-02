import type { Auth } from 'firebase/auth'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/firebase', () => ({ auth: {} }))

const { uploadLog } = await import('@/lib/upload')
const { ApiError } = await import('@/lib/api')

const auth = { currentUser: { getIdToken: async () => 'token' } } as unknown as Auth

/** Just enough of XMLHttpRequest to drive uploadLog: the test decides how the request ends. */
class FakeXhr {
  static last: FakeXhr
  upload: { onprogress?: (e: Partial<ProgressEvent>) => void; onload?: () => void } = {}
  onload?: () => void
  onerror?: () => void
  responseType = ''
  status = 0
  statusText = ''
  response: unknown = null
  method = ''
  url = ''
  headers: Record<string, string> = {}
  body: FormData | null = null

  constructor() {
    FakeXhr.last = this
  }
  open(method: string, url: string) {
    this.method = method
    this.url = url
  }
  setRequestHeader(name: string, value: string) {
    this.headers[name] = value
  }
  send(body: FormData) {
    this.body = body
  }
  respond(status: number, response: unknown) {
    this.status = status
    this.response = response
    this.onload?.()
  }
}

afterEach(() => vi.unstubAllGlobals())

async function startUpload(onProgress = vi.fn()) {
  vi.stubGlobal('XMLHttpRequest', FakeXhr)
  const file = new File(['{}'], 'log.ndjson')
  const promise = uploadLog(file, onProgress, auth)
  await vi.waitFor(() => expect(FakeXhr.last?.body).toBeTruthy())
  return { promise, xhr: FakeXhr.last, file, onProgress }
}

describe('uploadLog', () => {
  it('posts the file with the token and reports progress', async () => {
    const { promise, xhr, file, onProgress } = await startUpload()
    expect(xhr.method).toBe('POST')
    expect(xhr.url).toBe('/api/uploads')
    expect(xhr.headers.Authorization).toBe('Bearer token')
    expect(xhr.body?.get('file')).toBe(file)

    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 200 })
    xhr.upload.onload?.()
    expect(onProgress.mock.calls).toEqual([[0.25], [1]])

    xhr.respond(201, { id: 'abc', filename: 'log.ndjson' })
    await expect(promise).resolves.toMatchObject({ id: 'abc' })
  })

  it('rejects with the API error, details included', async () => {
    const { promise, xhr } = await startUpload()
    xhr.respond(409, {
      error: { code: 'duplicate_upload', message: 'You already uploaded this file.', existing_upload_id: 'abc' },
    })

    const error = await promise.catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 409, code: 'duplicate_upload', details: { existing_upload_id: 'abc' } })
  })

  it('rejects with a network error when the request never completes', async () => {
    const { promise, xhr } = await startUpload()
    xhr.onerror?.()
    await expect(promise).rejects.toMatchObject({ status: 0, code: 'network_error' })
  })
})
