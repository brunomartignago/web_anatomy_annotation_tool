"""ULIDs: 26-character ids that sort by creation time and are never reused.

Format: 48-bit millisecond timestamp + 80 random bits, Crockford base32.
"""

import os
import time

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_ulid(timestamp_ms: int | None = None, randomness: bytes | None = None) -> str:
    if timestamp_ms is None:
        timestamp_ms = time.time_ns() // 1_000_000
    if randomness is None:
        randomness = os.urandom(10)
    if not 0 <= timestamp_ms < 2**48 or len(randomness) != 10:
        raise ValueError("ULID needs a 48-bit timestamp and 10 random bytes")
    value = (timestamp_ms << 80) | int.from_bytes(randomness, "big")
    return "".join(_CROCKFORD[(value >> shift) & 31] for shift in range(125, -1, -5))


def ulid_timestamp_ms(ulid: str) -> int:
    value = 0
    for char in ulid:
        value = (value << 5) | _CROCKFORD.index(char)
    return value >> 80
