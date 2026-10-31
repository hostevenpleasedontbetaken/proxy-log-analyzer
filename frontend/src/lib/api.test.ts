import type { Auth } from 'firebase/auth'
import { afterEach, describe, expect, it, vi } from 'vitest'

const signOut = vi.fn()
vi.mock('firebase/auth', () => ({ signOut: (...args: unknown[]) => signOut(...args) }))
// Keep the real Firebase app from initializing in tests.
vi.mock('@/lib/firebase', () => ({ auth: {} }))

const { api, ApiError } = await import('@/lib/api')

function fakeAuth(): Auth {
  const getIdToken = vi.fn(async (force?: boolean) => (force ? 'fresh-token' : 'old-token'))
  return { currentUser: { getIdToken } } as unknown as Auth
}

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => {
  vi.unstubAllGlobals()
  signOut.mockReset()
})

describe('api()', () => {
  it('sends the ID token as a Bearer header', async () => {
    const fetchMock = vi.fn(async () => json(200, { ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(api('/me', {}, fakeAuth())).resolves.toEqual({ ok: true })
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/me')
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer old-token')
  })

  it('refreshes the token and retries once on 401', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(401, { error: { code: 'unauthenticated', message: 'expired' } }))
      .mockResolvedValueOnce(json(200, { ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(api('/me', {}, fakeAuth())).resolves.toEqual({ ok: true })
    const retryInit = fetchMock.mock.calls[1][1] as RequestInit
    expect(new Headers(retryInit.headers).get('Authorization')).toBe('Bearer fresh-token')
    expect(signOut).not.toHaveBeenCalled()
  })

  it('signs out when the retry is still 401', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(401, { error: { code: 'unauthenticated', message: 'nope' } })))

    await expect(api('/me', {}, fakeAuth())).rejects.toMatchObject({ status: 401, code: 'unauthenticated' })
    expect(signOut).toHaveBeenCalledOnce()
  })

  it('turns the error envelope into an ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(404, { error: { code: 'not_found', message: 'Upload not found' } })))

    const error = await api('/uploads/x', {}, fakeAuth()).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 404, code: 'not_found', message: 'Upload not found' })
  })
})
