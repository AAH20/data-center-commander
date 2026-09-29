"""Example: Time-series interval alignment.

Aligns data sampled at different intervals to a common grid.
"""
from dcc.validation.intervals import align_timestamp, floor_timestamp, interval_seconds
from datetime import datetime, timezone

ts = datetime(2026, 1, 15, 14, 23, 45, tzinfo=timezone.utc)
aligned = align_timestamp(ts, interval_seconds("15min"))
print(f"Original: {ts}")
print(f"Aligned to 15min: {aligned}")

floored = floor_timestamp(ts, interval_seconds("1hr"))
print(f"Floored to 1hr: {floored}")
