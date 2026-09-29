"""Example: Completeness scoring.

Measures the fraction of required fields present and non-null.
"""
from dcc.quality.engine import completeness_score

records = [
    {"id": "1", "name": "A", "value": 100},
    {"id": "2", "name": None, "value": 200},
    {"id": "3", "name": "C", "value": None},
]
score = completeness_score(records, required_fields=["id", "name", "value"])
print(f"Completeness: {score.score:.2%}")
print(f"Passed: {score.passed}/{score.total}")
