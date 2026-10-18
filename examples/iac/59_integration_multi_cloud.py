"""Example: Multi-cloud compliance check.

Demonstrates checking compliance across AWS, Azure, and GCP resources.
"""
from dcc.iac_observability.compliance import ComplianceEngine, get_default_checks

# Multi-cloud resources
resources = [
    # AWS
    {"id": "aws-1", "resource_type": "aws_instance", "encrypted": True,
     "publicly_accessible": False, "tags": {"env": "prod"}, "logging_enabled": True},
    # Azure
    {"id": "azure-1", "resource_type": "azure_vm", "encrypted": True,
     "publicly_accessible": False, "tags": {"env": "prod"}, "logging_enabled": True},
    # GCP
    {"id": "gcp-1", "resource_type": "gcp_instance", "encrypted": True,
     "publicly_accessible": False, "tags": {"env": "prod"}, "logging_enabled": True},
    # Non-compliant resource
    {"id": "aws-2", "resource_type": "aws_s3_bucket", "encrypted": False,
     "publicly_accessible": True, "tags": {}, "logging_enabled": False},
]

engine = ComplianceEngine(get_default_checks())
report = engine.evaluate(resources)
print(f"Total checks: {report.total_checks}")
print(f"Passed: {report.passed}")
print(f"Failed: {report.failed}")
print(f"Compliance rate: {report.compliance_rate:.1%}")
print(f"Overall status: {report.overall_status.value}")
