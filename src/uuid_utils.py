"""UUID <-> Ledger UniqueID (sint64 high, sint64 low) conversion.

Matches the encoding in the Kotlin client:
  high = (uuid.msb as sint64)
  low  = (uuid.lsb as sint64)
"""

import uuid


def uuid_to_high_low(u: uuid.UUID) -> tuple[int, int]:
    """Convert a UUID to (high, low) sint64 pair for Ledger UniqueID."""
    high = (u.int >> 64) & 0xFFFFFFFFFFFFFFFF
    low = u.int & 0xFFFFFFFFFFFFFFFF
    # Convert unsigned 64-bit to signed 64-bit (sint64)
    if high >= (1 << 63):
        high -= 1 << 64
    if low >= (1 << 63):
        low -= 1 << 64
    return high, low


def high_low_to_uuid(high: int, low: int) -> uuid.UUID:
    """Convert (high, low) sint64 pair back to a UUID."""
    # Convert signed to unsigned
    if high < 0:
        high += 1 << 64
    if low < 0:
        low += 1 << 64
    return uuid.UUID(int=(high << 64) | low)
