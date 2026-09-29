"""Example: Resample time-series data.

Downsamples high-frequency data to a lower frequency.
"""
from dcc.validation.intervals import resample, DataPoint, Aggregation
from datetime import datetime, timedelta

base = datetime(2026, 1, 1)
points = [
    DataPoint(timestamp=base + timedelta(minutes=i), value=100 + i)
    for i in range(60)
]
resampled = resample(points, interval=300, aggregation=Aggregation.MEAN)
print(f"Original: {len(points)} points")
print(f"Resampled to 5min: {len(resampled)} points")
for p in resampled[:3]:
    print(f"  {p.timestamp}: {p.value:.1f}")
