import { formatBytes, formatCount, formatTimestamp } from '@/lib/format'
import type { EntryDetail } from '@/lib/types'

// Grouped the way an analyst reads an entry: who, what was requested, what Zscaler decided,
// and any file or threat involved. Empty fields are left out.
const GROUPS: { title: string; fields: [label: string, value: (e: EntryDetail) => string | number | null][] }[] = [
  {
    title: 'Who',
    fields: [
      ['User', (e) => e.login],
      ['Department', (e) => e.dept],
      ['Device', (e) => e.devicehostname],
      ['Client IP', (e) => e.cltip],
      ['Location', (e) => e.location],
      ['User agent', (e) => e.useragent],
    ],
  },
  {
    title: 'Request',
    fields: [
      ['Time (UTC)', (e) => formatTimestamp(e.ts)],
      ['Method', (e) => e.reqmethod],
      ['URL', (e) => e.url],
      ['Referrer', (e) => e.refererhost],
      ['Server IP', (e) => e.serverip],
      ['Country', (e) => e.dstip_country],
      ['Protocol', (e) => e.proto],
      ['Sent', (e) => (e.reqsize !== null ? formatBytes(e.reqsize) : null)],
      ['Received', (e) => (e.respsize !== null ? formatBytes(e.respsize) : null)],
      ['Status', (e) => e.respcode],
      ['Content type', (e) => e.contenttype],
    ],
  },
  {
    title: 'Zscaler decision',
    fields: [
      ['Action', (e) => e.action],
      ['Reason', (e) => e.reason],
      ['Rule', (e) => e.rulelabel],
      ['Category', (e) => [e.urlsupercat, e.urlsubcat].filter(Boolean).join(' › ') || null],
      ['Class', (e) => e.urlclass],
      ['App', (e) => e.appname],
      ['Risk score', (e) => (e.riskscore !== null ? `${e.riskscore}/100` : null)],
    ],
  },
  {
    title: 'File and threat',
    fields: [
      ['Threat', (e) => e.threatname],
      ['Threat severity', (e) => e.threatseverity],
      ['Malware', (e) => [e.malwarecategory, e.malwareclass].filter(Boolean).join(' › ') || null],
      ['File', (e) => e.filename],
      ['File type', (e) => e.filetype],
      ['Uploaded file', (e) => e.upload_filename],
      ['SHA-256', (e) => e.sha256],
    ],
  },
]

/** Every stored field of one entry, grouped, plus where it came from in the file. */
export function EntryFields({ entry }: { entry: EntryDetail }) {
  return (
    <div className="grid gap-4">
      {GROUPS.map((group) => {
        const rows = group.fields
          .map(([label, value]) => [label, value(entry)] as const)
          .filter(([, value]) => value !== null && value !== '')
        if (rows.length === 0) return null
        return (
          <section key={group.title} className="grid gap-1.5">
            <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{group.title}</h3>
            <dl className="grid grid-cols-[8rem_1fr] gap-x-3 gap-y-1">
              {rows.map(([label, value]) => (
                <div key={label} className="contents">
                  <dt className="text-muted-foreground">{label}</dt>
                  <dd className="break-all">{value}</dd>
                </div>
              ))}
            </dl>
          </section>
        )
      })}
      {/* Not the Zscaler record id: those are ~7×10^18, past what a JS number holds exactly. */}
      <p className="text-xs text-muted-foreground">Line {formatCount(entry.line_no)} of the uploaded file</p>
    </div>
  )
}
