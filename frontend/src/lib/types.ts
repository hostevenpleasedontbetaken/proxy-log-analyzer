/** Shapes of the backend's JSON responses (see backend/app/schemas.py). */

export type UploadSummary = {
  id: string
  filename: string
  size_bytes: number
  status: string
  line_count: number | null
  parsed_count: number | null
  error_count: number | null
  time_start: string | null
  time_end: string | null
  created_at: string
}

export type Band = 'High' | 'Medium' | 'Low'

export type DetectionSummary = {
  incidents: number
  anomalies: number
  incidents_by_band: Record<Band, number>
  incidents_by_severity: Record<string, number>
  ml: { ran: boolean; active_user_hours: number; required_user_hours: number }
}

export type UploadDetail = UploadSummary & {
  parse_errors: { line: number; reason: string; excerpt: string }[] | null
  // Precomputed at upload time; typed loosely here and narrowed where the Overview reads it.
  stats: ({ detection: DetectionSummary } & Record<string, unknown>) | null
  parser_version: string | null
  detector_version: string | null
  processed_at: string | null
}
