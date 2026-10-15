import { describe, expect, it } from 'vitest'

import { newUlid } from './ids'

const CROCKFORD = /^[0-9A-HJKMNP-TV-Z]{26}$/

describe('newUlid', () => {
  it('has the same 26-character Crockford format as the backend', () => {
    expect(newUlid()).toMatch(CROCKFORD)
  })

  it('is unique', () => {
    expect(new Set(Array.from({ length: 1000 }, () => newUlid())).size).toBe(1000)
  })

  it('sorts by creation time', () => {
    expect(newUlid(1_000) < newUlid(2_000)).toBe(true)
  })

  it('matches the backend encoding for a known value', () => {
    // backend/tests/test_ids.py: timestamp 1 with zero randomness.
    expect(newUlid(1, new Uint8Array(10))).toBe('0000000001' + '0'.repeat(16))
  })
})
