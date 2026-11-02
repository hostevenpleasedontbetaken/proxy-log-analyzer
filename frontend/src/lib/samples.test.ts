import { describe, expect, it } from 'vitest'
import { dataUrlBytes } from '@/lib/samples'

describe('dataUrlBytes', () => {
  it('decodes base64 into the original bytes (gzip magic bytes survive)', () => {
    expect([...dataUrlBytes('data:application/gzip;base64,H4sIAAAA')]).toEqual([0x1f, 0x8b, 0x08, 0, 0, 0])
  })
})
