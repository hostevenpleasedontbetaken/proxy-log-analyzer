import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatCount } from '@/lib/format'
import type { UploadDetail, UploadStats } from '@/lib/types'

type Props = { quality: UploadStats['quality']; parseErrors: UploadDetail['parse_errors'] }

/** How much of the file was usable: skipped lines (with the first few reasons) and field warnings. */
export function DataQuality({ quality, parseErrors }: Props) {
  const warnings = Object.entries(quality.warnings)

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>Parsing</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 text-sm">
        <p>
          {formatCount(quality.parsed)} of {formatCount(quality.lines)} lines parsed
          {quality.errors > 0 ? `; ${formatCount(quality.errors)} skipped.` : ', none skipped.'}
        </p>
        {warnings.length > 0 && (
          <div className="grid gap-1">
            <p className="text-muted-foreground">Fields that couldn't be read (the rest of the line was kept):</p>
            <ul className="list-inside list-disc">
              {warnings.map(([warning, count]) => (
                <li key={warning}>
                  {warning}: {formatCount(count)}
                </li>
              ))}
            </ul>
          </div>
        )}
        {parseErrors && parseErrors.length > 0 && (
          <details>
            <summary className="cursor-pointer text-muted-foreground">
              First {parseErrors.length} skipped lines
            </summary>
            <ul className="mt-2 grid gap-2">
              {parseErrors.map((error) => (
                <li key={error.line}>
                  <span className="font-medium">Line {error.line}:</span> {error.reason}
                  {error.excerpt && (
                    <code className="mt-0.5 block truncate rounded bg-muted px-1.5 py-0.5 text-xs">{error.excerpt}</code>
                  )}
                </li>
              ))}
            </ul>
          </details>
        )}
      </CardContent>
    </Card>
  )
}
