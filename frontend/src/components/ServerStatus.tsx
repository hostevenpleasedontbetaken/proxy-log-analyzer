import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { api } from '@/lib/api'

const SLOW_AFTER_MS = 2000

/**
 * Pings /api/health when the page opens. The free-tier API and database both sleep when idle,
 * so the first request after a pause can take ~10–15 s; this explains the wait instead of
 * leaving the page looking stuck. Shows nothing when the server answers quickly.
 */
export function ServerStatus() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => api<{ status: string }>('/health'),
    staleTime: Infinity,
  })
  const [slow, setSlow] = useState(false)

  useEffect(() => {
    if (!health.isPending) return
    const timer = setTimeout(() => setSlow(true), SLOW_AFTER_MS)
    return () => clearTimeout(timer)
  }, [health.isPending])

  if (health.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>The server isn't responding. Try again in a minute.</AlertDescription>
      </Alert>
    )
  }
  if (health.isPending && slow) {
    return (
      <Alert role="status">
        <AlertDescription>Waking up the server… the first request after a quiet spell takes a few seconds.</AlertDescription>
      </Alert>
    )
  }
  return null
}
