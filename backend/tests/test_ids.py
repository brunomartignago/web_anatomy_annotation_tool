import re

from annotool.ids import new_ulid, ulid_timestamp_ms

CROCKFORD = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def test_ulid_shape():
    assert CROCKFORD.match(new_ulid())


def test_ulids_are_unique():
    assert len({new_ulid() for _ in range(1000)}) == 1000


def test_ulid_encodes_timestamp_and_sorts_by_time():
    early = new_ulid(timestamp_ms=1_000)
    late = new_ulid(timestamp_ms=2_000)
    assert ulid_timestamp_ms(early) == 1_000
    assert early < late


def test_ulid_known_value():
    # All-zero randomness makes the output deterministic.
    assert new_ulid(timestamp_ms=0, randomness=bytes(10)) == "0" * 26
    # 10 characters of timestamp, then 16 of randomness.
    assert new_ulid(timestamp_ms=1, randomness=bytes(10)) == "0000000001" + "0" * 16
