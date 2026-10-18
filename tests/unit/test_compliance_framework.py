"""Unit tests for the compliance-as-code framework."""
import unittest
from datetime import datetime, timezone

from dcc.compliance.models import (
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
from dcc.compliance.scanner import ComplianceScanner
from dcc.compliance.controls import get_builtin_controls, get_controls_by_framework
from dcc.compliance.unified import UnifiedComplianceEngine, PolicyEngineIntegration
from dcc.compliance.providers import (
    AWSComplianceProvider,
    AzureComplianceProvider,
    GCPComplianceProvider,
    DigitalOceanComplianceProvider,
    IBMComplianceProvider,
)
from dcc.compliance.providers.base import ProviderComplianceResult, ProviderComplianceStatus
from dcc.compliance.remediation import CloudRemediationEngine
from dcc.compliance.integrations import (
    ComplianceIntegrationRunner,
    IntegrationType,
    AWSConfigIntegration,
    AzurePolicyIntegration,
    GCPSCCIntegration,
    OPARegoIntegration,
    SentinelIntegration,
    CheckovIntegration,
    TfsecIntegration,
)


class TestProviderCompliance(unittest.TestCase):
    """Test cloud provider compliance modules."""

    def test_aws_provider_name(self):
        provider = AWSComplianceProvider()
        self.assertEqual(provider.provider_name, "aws")

    def test_azure_provider_name(self):
        provider = AzureComplianceProvider()
        self.assertEqual(provider.provider_name, "azure")

    def test_gcp_provider_name(self):
        provider = GCPComplianceProvider()
        self.assertEqual(provider.provider_name, "gcp")

    def test_digitalocean_provider_name(self):
        provider = DigitalOceanComplianceProvider()
        self.assertEqual(provider.provider_name, "digitalocean")

    def test_ibm_provider_name(self):
        provider = IBMComplianceProvider()
        self.assertEqual(provider.provider_name, "ibm")

    def test_aws_s3_encryption_pass(self):
        provider = AWSComplianceProvider()
        resource = {"id": "bucket-1", "resource_type": "aws_s3_bucket", "encrypted": True}
        result = provider.evaluate(resource)
        self.assertEqual(result.status, ProviderComplianceStatus.PASS)

    def test_aws_s3_encryption_fail(self):
        provider = AWSComplianceProvider()
        resource = {"id": "bucket-1", "resource_type": "aws_s3_bucket", "encrypted": False}
        result = provider.evaluate(resource)
        self.assertEqual(result.status, ProviderComplianceStatus.FAIL)

    def test_aws_s3_public_access_fail(self):
        provider = AWSComplianceProvider()
        resource = {"id": "bucket-1", "resource_type": "aws_s3_bucket", "publicly_accessible": True}
        result = provider.evaluate(resource)
        self.assertEqual(result.status, ProviderComplianceStatus.FAIL)

    def test_azure_storage_encryption_pass(self):
        provider = AzureComplianceProvider()
        resource = {"id": "storage-1", "resource_type": "azurerm_storage_account", "encrypted": True}
        result = provider.evaluate(resource)
        self.assertEqual(result.status, ProviderComplianceStatus.PASS)

    def test_gcp_gcs_uniform_access_fail(self):
        provider = GCPComplianceProvider()
        resource = {"id": "bucket-1", "resource_type": "google_storage_bucket", "uniform_bucket_level_access": False}
        result = provider.evaluate(resource)
        self.assertEqual(result.status, ProviderComplianceStatus.FAIL)

    def test_do_spaces_private_pass(self):
        provider = DigitalOceanComplianceProvider()
        resource = {"id": "bucket-1", "resource_type": "digitalocean_spaces_bucket", "acl": "private"}
        result = provider.evaluate(resource)
        self.assertEqual(result.status, ProviderComplianceStatus.PASS)

    def test_ibm_cos_encryption_fail(self):
        provider = IBMComplianceProvider()
        resource = {"id": "bucket-1", "resource_type": "ibm_cos_bucket", "encryption_enabled": False}
        result = provider.evaluate(resource)
        self.assertEqual(result.status, ProviderComplianceStatus.FAIL)

    def test_unknown_resource_type(self):
        provider = AWSComplianceProvider()
        resource = {"id": "unknown-1", "resource_type": "unknown_type"}
        result = provider.evaluate(resource)
        self.assertEqual(result.status, ProviderComplianceStatus.NOT_APPLICABLE)

    def test_evaluate_all(self):
        provider = AWSComplianceProvider()
        resources = [
            {"id": "bucket-1", "resource_type": "aws_s3_bucket", "encrypted": True},
            {"id": "bucket-2", "resource_type": "aws_s3_bucket", "encrypted": False},
        ]
        results = provider.evaluate_all(resources)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].status, ProviderComplianceStatus.PASS)
        self.assertEqual(results[1].status, ProviderComplianceStatus.FAIL)


class TestUnifiedComplianceEngine(unittest.TestCase):
    """Test the unified compliance engine."""

    def test_engine_creation(self):
        engine = UnifiedComplianceEngine()
        self.assertEqual(len(engine.providers), 5)

    def test_scan_empty_resources(self):
        engine = UnifiedComplianceEngine()
        report = engine.scan({})
        self.assertEqual(report.total_controls, 0)

    def test_scan_aws_resources(self):
        engine = UnifiedComplianceEngine()
        resources = {
            "aws": [
                {"id": "bucket-1", "resource_type": "aws_s3_bucket", "encrypted": True},
                {"id": "bucket-2", "resource_type": "aws_s3_bucket", "encrypted": False},
            ]
        }
        report = engine.scan(resources)
        self.assertGreater(report.total_controls, 0)

    def test_scan_multi_cloud(self):
        engine = UnifiedComplianceEngine()
        resources = {
            "aws": [{"id": "bucket-1", "resource_type": "aws_s3_bucket", "encrypted": True}],
            "azure": [{"id": "storage-1", "resource_type": "azurerm_storage_account", "encrypted": True}],
            "gcp": [{"id": "bucket-1", "resource_type": "google_storage_bucket", "uniform_bucket_level_access": True}],
        }
        report = engine.scan(resources)
        self.assertGreater(report.total_controls, 0)

    def test_scan_provider(self):
        engine = UnifiedComplianceEngine()
        resources = [{"id": "bucket-1", "resource_type": "aws_s3_bucket", "encrypted": True}]
        results = engine.scan_provider("aws", resources)
        self.assertGreater(len(results), 0)

    def test_get_provider_checks(self):
        engine = UnifiedComplianceEngine()
        checks = engine.get_provider_checks("aws")
        self.assertGreater(len(checks), 0)


class TestPolicyEngineIntegration(unittest.TestCase):
    """Test the policy engine integration."""

    def test_integration_creation(self):
        integration = PolicyEngineIntegration()
        self.assertIsNotNone(integration)

    def test_list_policies(self):
        integration = PolicyEngineIntegration()
        policies = integration.list_policies()
        self.assertIn("opa", policies)
        self.assertIn("sentinel", policies)
        self.assertGreater(len(policies["opa"]), 0)
        self.assertGreater(len(policies["sentinel"]), 0)

    def test_evaluate_opa(self):
        integration = PolicyEngineIntegration()
        input_doc = {
            "resources": [
                {"id": "bucket-1", "encrypted": True},
                {"id": "bucket-2", "encrypted": False},
            ]
        }
        result = integration.evaluate_opa("aws_encryption", input_doc)
        self.assertIn("violations", result)
        self.assertIn("compliant", result)

    def test_evaluate_sentinel(self):
        integration = PolicyEngineIntegration()
        input_doc = {
            "resources": [
                {"id": "bucket-1", "encrypted": True},
            ]
        }
        result = integration.evaluate_sentinel("aws_encryption", input_doc)
        self.assertIn("violations", result)
        self.assertIn("compliant", result)


class TestCloudRemediation(unittest.TestCase):
    """Test cloud remediation engine."""

    def test_engine_creation(self):
        engine = CloudRemediationEngine()
        self.assertIsNotNone(engine)

    def test_create_from_results(self):
        engine = CloudRemediationEngine()
        results = [
            ProviderComplianceResult(
                check_id="AWS-S3-001",
                provider="aws",
                name="S3 Bucket Encryption",
                status=ProviderComplianceStatus.FAIL,
                severity="high",
                category="security",
                detail="S3 bucket does not have server-side encryption",
            )
        ]
        actions = engine.create_from_results(results)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].provider, "aws")

    def test_dry_run(self):
        engine = CloudRemediationEngine(dry_run=True)
        self.assertTrue(engine.dry_run)


class TestComplianceIntegrations(unittest.TestCase):
    """Test compliance integrations."""

    def test_aws_config_integration(self):
        integration = AWSConfigIntegration()
        result = integration.run({})
        self.assertEqual(result.integration_type, IntegrationType.AWS_CONFIG)
        self.assertEqual(result.status, "completed")

    def test_azure_policy_integration(self):
        integration = AzurePolicyIntegration()
        result = integration.run({})
        self.assertEqual(result.integration_type, IntegrationType.AZURE_POLICY)
        self.assertEqual(result.status, "completed")

    def test_gcp_scc_integration(self):
        integration = GCPSCCIntegration()
        result = integration.run({})
        self.assertEqual(result.integration_type, IntegrationType.GCP_SCC)
        self.assertEqual(result.status, "completed")

    def test_opa_rego_integration(self):
        integration = OPARegoIntegration()
        result = integration.run({})
        self.assertEqual(result.integration_type, IntegrationType.OPA_REGO)
        self.assertEqual(result.status, "completed")

    def test_sentinel_integration(self):
        integration = SentinelIntegration()
        result = integration.run({})
        self.assertEqual(result.integration_type, IntegrationType.SENTINEL)
        self.assertEqual(result.status, "completed")

    def test_checkov_integration(self):
        integration = CheckovIntegration()
        result = integration.run({})
        self.assertEqual(result.integration_type, IntegrationType.CHECKOV)
        self.assertEqual(result.status, "completed")

    def test_tfsec_integration(self):
        integration = TfsecIntegration()
        result = integration.run({})
        self.assertEqual(result.integration_type, IntegrationType.TFSEC)
        self.assertEqual(result.status, "completed")

    def test_integration_runner(self):
        runner = ComplianceIntegrationRunner()
        results = runner.run_all({})
        self.assertEqual(len(results), 7)

    def test_integration_report(self):
        runner = ComplianceIntegrationRunner()
        results = runner.run_all({})
        report = runner.to_report(results)
        self.assertIn("total_integrations", report)
        self.assertIn("results", report)


class TestComplianceScanner(unittest.TestCase):
    """Test the compliance scanner with new controls."""

    def test_builtin_controls_count(self):
        controls = get_builtin_controls()
        self.assertGreater(len(controls), 0)

    def test_controls_by_framework(self):
        soc2_controls = get_controls_by_framework(Framework.SOC2)
        self.assertGreater(len(soc2_controls), 0)

        iso_controls = get_controls_by_framework(Framework.ISO27001)
        self.assertGreater(len(iso_controls), 0)

        pci_controls = get_controls_by_framework(Framework.PCI_DSS)
        self.assertGreater(len(pci_controls), 0)

        hipaa_controls = get_controls_by_framework(Framework.HIPAA)
        self.assertGreater(len(hipaa_controls), 0)

        nist_controls = get_controls_by_framework(Framework.NIST_800_53)
        self.assertGreater(len(nist_controls), 0)

    def test_scanner_with_all_controls(self):
        scanner = ComplianceScanner()
        for ctrl in get_builtin_controls():
            scanner.register(ctrl)
        report = scanner.scan()
        self.assertGreater(report.total_controls, 0)


if __name__ == "__main__":
    unittest.main()
