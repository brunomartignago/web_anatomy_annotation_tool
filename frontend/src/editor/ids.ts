// ULIDs, the same format as backend/src/annotool/ids.py: 48-bit millisecond timestamp
// + 80 random bits, Crockford base32. They sort by creation time and are never reused.

const CROCKFORD = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'

export function newUlid(
  timestampMs: number = Date.now(),
  randomness: Uint8Array = crypto.getRandomValues(new Uint8Array(10)),
): string {
  let random = 0n
  for (const byte of randomness) random = (random << 8n) | BigInt(byte)
  const value = (BigInt(timestampMs) << 80n) | random
  let out = ''
  for (let shift = 125n; shift >= 0n; shift -= 5n) {
    out += CROCKFORD[Number((value >> shift) & 31n)]
  }
  return out
}
