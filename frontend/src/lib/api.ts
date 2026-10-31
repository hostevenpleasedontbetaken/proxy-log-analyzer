import { signOut, type Auth } from 'firebase/auth'
import { auth as defaultAuth } from '@/lib/firebase'

/** The backend's error envelope: {"error": {"code": "...", "message": "..."}}. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

/**
 * fetch() wrapper for every /api call.
 * - Attaches the Firebase ID token as `Authorization: Bearer ...`.
 * - On 401, forces a token refresh and retries once (the token may have just expired).
 * - If it is still 401, signs out so the app shows the login page.
 * - Turns error responses into ApiError so components can switch on `code`.
 */
export async function api<T>(path: string, init: RequestInit = {}, auth: Auth = defaultAuth): Promise<T> {
  const send = async (forceRefresh: boolean) => {
    const token = await auth.currentUser?.getIdToken(forceRefresh)
    const headers = new Headers(init.headers)
    if (token) headers.set('Authorization', `Bearer ${token}`)
    return fetch(`/api${path}`, { ...init, headers })
  }

  let res = await send(false)
  if (res.status === 401 && auth.currentUser) {
    res = await send(true)
    if (res.status === 401) await signOut(auth)
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const error = body?.error
    throw new ApiError(res.status, error?.code ?? 'http_error', error?.message ?? res.statusText)
  }
  return res.json() as Promise<T>
}
