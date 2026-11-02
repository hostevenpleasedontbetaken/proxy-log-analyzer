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

/** The n biggest groups plus the total of everything else (see `top()` in backend/app/stats.py). */
export type TopList = { items: { key: string; value: number }[]; other: number }

export type TimelineBucket = {
  t: string // bucket start, UTC
  allowed: number
  blocked: number
  threats: number
  flagged: number
  bytes_out: number
}

/** Everything the Overview shows, precomputed at upload time (backend/app/stats.py). */
export type UploadStats = {
  version: number
  totals: {
    requests: number
    users: number
    client_ips: number
    devices: number
    hosts: number
    blocked: number
    threat_hits: number
    flagged: number
    high_risk: number
    bytes_out: number
    bytes_in: number
  }
  top: {
    users_by_requests: TopList
    users_by_bytes_out: TopList
    hosts_by_requests: TopList
    hosts_by_bytes_out: TopList
    countries: TopList
    categories: TopList
    blocked_hosts: TopList
    block_reasons: TopList
    threats: TopList
  }
  breakdown: Record<'action' | 'respcode_class' | 'urlclass', Record<string, number>>
  timeline: { bucket_seconds: number; buckets: TimelineBucket[] }
  quality: { lines: number; parsed: number; errors: number; warnings: Record<string, number> }
  detection: DetectionSummary
}

export type UploadDetail = UploadSummary & {
  parse_errors: { line: number; reason: string; excerpt: string }[] | null
  stats: UploadStats | null
  parser_version: string | null
  detector_version: string | null
  processed_at: string | null
}

/** One detector's finding (backend AnomalyOut). */
export type Anomaly = {
  id: number
  incident_id: number | null
  detector: 'rule' | 'statistical' | 'ml'
  kind: string // which detector, e.g. "beaconing"
  subject_type: string
  subject: string
  title: string
  explanation: string
  confidence: number // 0..1
  severity: number // 1 Low … 4 Critical
  start_ts: string
  end_ts: string
  entry_count: number
  evidence: Record<string, unknown> | null
}

/** Findings about the same subject close together in time, with a combined confidence (backend IncidentOut). */
export type Incident = {
  id: number
  subject_type: string
  subject: string
  title: string
  summary: string | null
  severity: number
  confidence: number
  start_ts: string
  end_ts: string
  anomalies: Anomaly[]
}
