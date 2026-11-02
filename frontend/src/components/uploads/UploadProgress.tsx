import { LoaderCircle } from 'lucide-react'
import { Progress } from '@/components/ui/progress'

/** "Uploading… 40%" while the file is sent, then "Analyzing…" until the server responds. */
export function UploadProgress({ progress }: { progress: number }) {
  const analyzing = progress >= 1
  return (
    <div className="grid w-full max-w-sm gap-2" role="status">
      <p className="flex items-center justify-center gap-2 font-medium">
        <LoaderCircle className="size-4 animate-spin" aria-hidden />
        {analyzing ? 'Analyzing… parsing and running detection' : `Uploading… ${Math.round(progress * 100)}%`}
      </p>
      <Progress value={analyzing ? 100 : progress * 100} aria-label="Upload progress" />
    </div>
  )
}
