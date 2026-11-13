import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/auth/auth-context'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { UploadRow } from '@/components/uploads/UploadRow'
import { api } from '@/lib/api'
import type { UploadSummary } from '@/lib/types'

/** The signed-in user's uploads (plus the shared sample analysis), newest first. */
export function UploadsList() {
  const { user } = useAuth()
  const uploads = useQuery({
    queryKey: ['uploads'],
    queryFn: () => api<{ uploads: UploadSummary[] }>('/uploads'),
    select: (data) => data.uploads,
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>{user?.isAnonymous ? 'Sample analysis' : 'Your uploads'}</CardTitle>
      </CardHeader>
      <CardContent>
        {uploads.isPending && <p className="text-sm text-muted-foreground">Loading uploads…</p>}
        {uploads.isError && (
          <Alert variant="destructive">
            <AlertDescription>Couldn't load your uploads: {uploads.error.message}</AlertDescription>
          </Alert>
        )}
        {uploads.data?.length === 0 && (
          <p className="text-sm text-muted-foreground">No uploads yet. Drop a log above or try a sample.</p>
        )}
        {uploads.data && uploads.data.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>File</TableHead>
                <TableHead className="text-right">Entries</TableHead>
                <TableHead className="hidden md:table-cell">Log time range</TableHead>
                <TableHead className="hidden sm:table-cell">Uploaded</TableHead>
                <TableHead className="w-10">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {uploads.data.map((upload) => (
                <UploadRow key={upload.id} upload={upload} />
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}
