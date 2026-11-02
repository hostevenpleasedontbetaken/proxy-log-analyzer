import { signOut, type Auth } from 'firebase/auth'
import { auth as defaultAuth } from '@/lib/firebase'

/** The backend's error envelope: {"error": {"code": "...", "message": "...", ...details}}. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  /** Extra fields some errors carry, e.g. `existing_upload_id` on a duplicate upload. */
  readonly details: Record<string, unknown>

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

/** Builds an ApiError from a parsed error response body (which may not be our envelope). */
export function toApiError(status: number, body: unknown, statusText: string): ApiError {
  const error = (body as { error?: Record<string, unknown> } | null)?.error
  const { code, message, ...details } = error ?? {}
  return new ApiError(
    status,
    typeof code === 'string' ? code : 'http_error',
    typeof message === 'string' ? message : statusText || 'Request failed',
    details,
  )
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
    throw toApiError(res.status, await res.json().catch(() => null), res.statusText)
  }
  // 204 No Content (e.g. DELETE) has no body to parse.
  return (res.status === 204 ? undefined : res.json()) as Promise<T>
}
