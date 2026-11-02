// The repo's sample logs, bundled with the frontend so a reviewer can try the app without a
// Zscaler export at hand. Each is loaded only when its button is clicked.
import cleanUrl from '@samples/acme-web-clean.ndjson?url'
import smallUrl from '@samples/acme-web-small.ndjson?url'

export type Sample = { filename: string; label: string; description: string; load: () => Promise<Blob> }

export const SAMPLES: Sample[] = [
  {
    filename: 'acme-web-day.ndjson.gz',
    label: 'Full day',
    description: 'One day, 40 employees, all 8 planted attacks (18,654 lines)',
    // Inlined rather than served as a .gz file: servers may send that with
    // `Content-Encoding: gzip` (Vite's dev server does), and the browser would then un-gzip
    // it before we upload it: 20 MB instead of 1 MB, and a different file hash.
    load: async () => {
      const { default: dataUrl } = await import('@samples/acme-web-day.ndjson.gz?url&inline')
      return new Blob([dataUrlBytes(dataUrl)])
    },
  },
  {
    filename: 'acme-web-small.ndjson',
    label: 'Small',
    description: '5 employees, 3 attacks (1,934 lines)',
    load: () => fetchBlob(smallUrl),
  },
  {
    filename: 'acme-web-clean.ndjson',
    label: 'Clean',
    description: '12 employees, no attacks: checks false alarms',
    load: () => fetchBlob(cleanUrl),
  },
]

/** Loads a sample as a File, so it goes through the normal upload path. */
export async function loadSample(sample: Sample): Promise<File> {
  return new File([await sample.load()], sample.filename)
}

async function fetchBlob(url: string): Promise<Blob> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Couldn't load the sample (${res.status}).`)
  return res.blob()
}

/** Decodes a base64 data: URL by hand (fetching it would need `data:` in the CSP's connect-src). */
export function dataUrlBytes(dataUrl: string): Uint8Array<ArrayBuffer> {
  const binary = atob(dataUrl.slice(dataUrl.indexOf(',') + 1))
  return Uint8Array.from(binary, (char) => char.charCodeAt(0))
}
