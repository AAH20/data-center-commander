"""Compliance-as-code framework for Data Center Commander.

Provides automated compliance scanning, evidence collection, remediation
workflows, and report generation for major compliance frameworks including
SOC 2, ISO 27001, PCI DSS, HIPAA, and NIST 800-53.

Supports multi-cloud compliance scanning across AWS, Azure, GCP,
DigitalOcean, and IBM Cloud with policy engines including OPA/Rego,
Sentinel, Checkov, and tfsec.

Usage
-----

.. code-block:: python

    from dcc.compliance import ComplianceScanner, get_builtin_controls
    from dcc.compliance.models import Framework

    scanner = ComplianceScanner()
    for ctrl in get_builtin_controls():
        scanner.register(ctrl)

    report = scanner.scan(framework=Framework.SOC2)
    print(f"Compliance score: {report.compliance_score:.1f}%")
    report.save("soc2-report.json")

Multi-cloud usage:

.. code-block:: python

    from dcc.compliance.unified import UnifiedComplianceEngine

    engine = UnifiedComplianceEngine()
    resources = {
        "aws": [{"id": "bucket-1", "resource_type": "aws_s3_bucket", "encrypted": True}],
        "azure": [{"id": "storage-1", "resource_type": "azurerm_storage_account", "encrypted": True}],
    }
    report = engine.scan(resources)
    print(f"Multi-cloud compliance score: {report.compliance_score:.1f}%")
"""
from .models import (
    ComplianceReport,
    ComplianceStatus,
    ControlDefinition,
    ControlResult,
    Evidence,
    EvidenceType,
    Finding,
    Framework,
    RemediationAction,
    RemediationStatus,
    Severity,
)
from .scanner import (
    ComplianceScanner,
    ControlNotFoundError,
    DuplicateControlError,
    ScanContext,
    ScannerError,
)
from .controls import get_builtin_controls, get_controls_by_framework
from .remediation import (
    RemediationEngine,
    RemediationError,
    RemediationExecutionError,
    RemediationPlaybook,
    get_builtin_playbooks,
    CloudRemediationEngine,
    CloudRemediationAction,
    CloudRemediationError,
    CloudRemediationExecutionError,
)
from .evidence import (
    EvidenceCollector,
    EvidenceCollectionError,
    EvidenceSourceError,
    EvidenceStore,
)
from .report import (
    ReportExporter,
    generate_html_report,
    generate_json_report,
    generate_markdown_report,
)
from .unified import UnifiedComplianceEngine, PolicyEngineIntegration
from .providers import (
    CloudProviderCompliance,
    ProviderComplianceResult,
    AWSComplianceProvider,
    AzureComplianceProvider,
    GCPComplianceProvider,
    DigitalOceanComplianceProvider,
    IBMComplianceProvider,
)

__all__ = [
    # Models
    "ComplianceReport",
    "ComplianceStatus",
    "ControlDefinition",
    "ControlResult",
    "Evidence",
    "EvidenceType",
    "Finding",
    "Framework",
    "RemediationAction",
    "RemediationStatus",
    "Severity",
    # Scanner
    "ComplianceScanner",
    "ControlNotFoundError",
    "DuplicateControlError",
    "ScanContext",
    "ScannerError",
    # Controls
    "get_builtin_controls",
    "get_controls_by_framework",
    # Remediation
    "RemediationEngine",
    "RemediationError",
    "RemediationExecutionError",
    "RemediationPlaybook",
    "get_builtin_playbooks",
    # Evidence
    "EvidenceCollector",
    "EvidenceCollectionError",
    "EvidenceSourceError",
    "EvidenceStore",
    # Report
    "ReportExporter",
    "generate_html_report",
    "generate_json_report",
    "generate_markdown_report",
    # Unified multi-cloud
    "UnifiedComplianceEngine",
    "PolicyEngineIntegration",
    # Providers
    "CloudProviderCompliance",
    "ProviderComplianceResult",
    "AWSComplianceProvider",
    "AzureComplianceProvider",
    "GCPComplianceProvider",
    "DigitalOceanComplianceProvider",
    "IBMComplianceProvider",
]
