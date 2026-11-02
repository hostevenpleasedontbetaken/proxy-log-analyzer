import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { Link } from 'react-router'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api } from '@/lib/api'
import { formatBytes, formatCount, formatDateTime, formatTimeRange } from '@/lib/format'
import type { UploadSummary } from '@/lib/types'

/** The signed-in user's uploads, newest first. */
export function UploadsList() {
  const uploads = useQuery({
    queryKey: ['uploads'],
    queryFn: () => api<{ uploads: UploadSummary[] }>('/uploads'),
    select: (data) => data.uploads,
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Your uploads</CardTitle>
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

function UploadRow({ upload }: { upload: UploadSummary }) {
  return (
    <TableRow>
      <TableCell className="max-w-64">
        <Link to={`/uploads/${upload.id}`} className="block truncate font-medium hover:underline">
          {upload.filename}
        </Link>
        <span className="text-xs text-muted-foreground">{formatBytes(upload.size_bytes)}</span>
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {formatCount(upload.parsed_count ?? 0)}
        {!!upload.error_count && (
          <div className="text-xs text-muted-foreground">{formatCount(upload.error_count)} skipped</div>
        )}
      </TableCell>
      <TableCell className="hidden md:table-cell">{formatTimeRange(upload.time_start, upload.time_end)}</TableCell>
      <TableCell className="hidden sm:table-cell">{formatDateTime(upload.created_at)}</TableCell>
      <TableCell>
        <DeleteUploadButton upload={upload} />
      </TableCell>
    </TableRow>
  )
}

function DeleteUploadButton({ upload }: { upload: UploadSummary }) {
  const queryClient = useQueryClient()
  const remove = useMutation({
    mutationFn: () => api<void>(`/uploads/${upload.id}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ['upload', upload.id] })
      return queryClient.invalidateQueries({ queryKey: ['uploads'] })
    },
  })

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={`Delete ${upload.filename}`} disabled={remove.isPending}>
          <Trash2 />
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete {upload.filename}?</AlertDialogTitle>
          <AlertDialogDescription>
            This removes the upload and its analysis (entries, incidents and anomalies). It can't be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={() => remove.mutate()}>
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
