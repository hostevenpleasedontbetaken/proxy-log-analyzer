import type { Anomaly, Band } from '@/lib/types'

/** Same thresholds as the backend's `band()` (backend/app/detection/findings.py). */
export function band(confidence: number): Band {
  if (confidence >= 0.8) return 'High'
  if (confidence >= 0.5) return 'Medium'
  return 'Low'
}

/** 0.947 → "95%". */
export function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`
}

export const SEVERITY_NAMES: Record<number, string> = { 1: 'Low', 2: 'Medium', 3: 'High', 4: 'Critical' }

export const DETECTOR_NAMES: Record<Anomaly['detector'], string> = {
  rule: 'Rule',
  statistical: 'Statistics',
  ml: 'Machine learning',
}
