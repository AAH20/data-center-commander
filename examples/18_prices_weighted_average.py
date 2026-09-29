"""Example: Weighted average price across multiple observations.

Computes a confidence-weighted average from multiple price sources.
"""
from dcc.economics.prices import compute_weighted_average_price

observations = [
    {"unit_price": 100, "confidence": 0.9, "quantity": 10},
    {"unit_price": 110, "confidence": 0.7, "quantity": 5},
    {"unit_price": 95, "confidence": 0.8, "quantity": 8},
]
result = compute_weighted_average_price(observations)
print(f"Weighted avg: ${result:.2f}")
