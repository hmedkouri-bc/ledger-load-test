"""Tests for UUID <-> UniqueID conversion."""

import uuid

from src.uuid_utils import uuid_to_high_low, high_low_to_uuid


def test_round_trip_random():
    """Random UUIDs should survive round-trip conversion."""
    for _ in range(100):
        u = uuid.uuid4()
        high, low = uuid_to_high_low(u)
        assert high_low_to_uuid(high, low) == u


def test_zero_uuid():
    u = uuid.UUID(int=0)
    high, low = uuid_to_high_low(u)
    assert high == 0
    assert low == 0
    assert high_low_to_uuid(high, low) == u


def test_max_uuid():
    u = uuid.UUID(int=(1 << 128) - 1)
    high, low = uuid_to_high_low(u)
    assert high == -1  # all bits set -> -1 as signed
    assert low == -1
    assert high_low_to_uuid(high, low) == u


def test_known_uuid():
    """Verify a known UUID produces correct high/low values."""
    u = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
    high, low = uuid_to_high_low(u)
    # Reconstruct and verify
    assert high_low_to_uuid(high, low) == u
    # High should be positive (MSB bit not set for this UUID)
    assert high > 0


def test_negative_high():
    """UUID with MSB set should produce negative high."""
    u = uuid.UUID("f50e8400-e29b-41d4-a716-446655440000")
    high, low = uuid_to_high_low(u)
    assert high < 0
    assert high_low_to_uuid(high, low) == u


def test_negative_low():
    """UUID with bit 63 of low set should produce negative low."""
    u = uuid.UUID("550e8400-e29b-41d4-f716-446655440000")
    high, low = uuid_to_high_low(u)
    assert low < 0
    assert high_low_to_uuid(high, low) == u


def test_sint64_range():
    """All values must fit in sint64 range."""
    for _ in range(100):
        u = uuid.uuid4()
        high, low = uuid_to_high_low(u)
        assert -(1 << 63) <= high < (1 << 63)
        assert -(1 << 63) <= low < (1 << 63)
