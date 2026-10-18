"""Cloud provider compliance modules.

Each provider module implements the CloudProviderCompliance interface
for scanning and evaluating compliance against provider-specific
security and configuration standards.
"""
from .base import CloudProviderCompliance, ProviderComplianceResult
from .aws import AWSComplianceProvider
from .azure import AzureComplianceProvider
from .gcp import GCPComplianceProvider
from .digitalocean import DigitalOceanComplianceProvider
from .ibm import IBMComplianceProvider

__all__ = [
    "CloudProviderCompliance",
    "ProviderComplianceResult",
    "AWSComplianceProvider",
    "AzureComplianceProvider",
    "GCPComplianceProvider",
    "DigitalOceanComplianceProvider",
    "IBMComplianceProvider",
]
