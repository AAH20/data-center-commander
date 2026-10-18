"""Example: Summarize drift results.

Demonstrates creating a summary of drift results for dashboard display.
"""
from dcc.iac_observability.drift import DriftDetector, summarize_drift

desired = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.micro"},
    "i-456": {"resource_type": "aws_instance", "name": "web-2", "instance_type": "t3.micro"},
    "i-789": {"resource_type": "aws_instance", "name": "db-1", "instance_type": "t3.small"},
}
actual = {
    "i-123": {"resource_type": "aws_instance", "name": "web-1", "instance_type": "t3.large"},
    "i-456": {"resource_type": "aws_instance", "name": "web-2", "instance_type": "t3.micro"},
    "i-999": {"resource_type": "aws_instance", "name": "rogue", "instance_type": "t3.micro"},
}

detector = DriftDetector()
result = detector.detect(desired, actual)
summary = summarize_drift(result)
print(f"Total drifted: {summary['total_drifted']}")
print(f"Drift rate: {summary['drift_rate']:.2%}")
print(f"Has drift: {summary['has_drift']}")
print(f"Severity counts: {summary['severity_counts']}")
print(f"Top drifts: {len(summary['top_drifts'])}")
