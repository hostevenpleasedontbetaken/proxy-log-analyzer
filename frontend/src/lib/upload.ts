import type { Auth } from 'firebase/auth'
import { ApiError, toApiError } from '@/lib/api'
import { auth as defaultAuth } from '@/lib/firebase'
import type { UploadDetail } from '@/lib/types'

/**
 * POST /api/uploads with upload progress.
 *
 * Uses XMLHttpRequest rather than fetch() because fetch can't report how much of the request
 * body has been sent. `onProgress` gets 0..1 while the file uploads; once it reaches 1 the
 * server is parsing and analysing, which the caller shows as "Analyzing…".
 */
export async function uploadLog(
  file: File,
  onProgress: (fraction: number) => void,
  auth: Auth = defaultAuth,
): Promise<UploadDetail> {
  // getIdToken() refreshes the token itself if it is about to expire.
  const token = await auth.currentUser?.getIdToken()
  const form = new FormData()
  form.append('file', file)

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/uploads')
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.responseType = 'json'

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total)
    }
    xhr.upload.onload = () => onProgress(1)
    xhr.onload = () => {
      if (xhr.status === 201) resolve(xhr.response as UploadDetail)
      else reject(toApiError(xhr.status, xhr.response, xhr.statusText))
    }
    xhr.onerror = () => reject(new ApiError(0, 'network_error', 'Could not reach the server. Check your connection and try again.'))
    xhr.send(form)
  })
}
