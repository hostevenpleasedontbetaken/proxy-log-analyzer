import { describe, expect, it } from 'vitest'
import { band, formatConfidence } from '@/lib/confidence'

describe('band', () => {
  it.each([
    [0.95, 'High'],
    [0.8, 'High'],
    [0.79, 'Medium'],
    [0.5, 'Medium'],
    [0.49, 'Low'],
    [0, 'Low'],
  ])('%d → %s', (confidence, expected) => {
    expect(band(confidence)).toBe(expected)
  })
})

describe('formatConfidence', () => {
  it('rounds to a whole percent', () => {
    expect(formatConfidence(0.947)).toBe('95%')
    expect(formatConfidence(0.35)).toBe('35%')
  })
})
