"""
GCP Compliance Module Tests
============================
Tests for GCP compliance modules: Cloud Audit Logs, Organization Policies, Security Command Center, VPC Service Controls.
"""

import os
import re
import unittest
from pathlib import Path

from tests.terraform.terraform_parser import TerraformParser, get_module_path


MODULES_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "iac", "modules"))


class TestGCPCloudAuditLogsModule(unittest.TestCase):
    """Tests for the GCP Cloud Audit Logs module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "gcp-compliance", "cloud-audit-logs")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Cloud Audit Logs module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_project_audit_config(self):
        """Project audit config resource exists."""
        self.assertIn("google_project_iam_audit_config.project", self.parsed["resources"])

    def test_folder_audit_config(self):
        """Folder audit config resource exists."""
        self.assertIn("google_folder_iam_audit_config.folder", self.parsed["resources"])

    def test_organization_audit_config(self):
        """Organization audit config resource exists."""
        self.assertIn("google_organization_iam_audit_config.organization", self.parsed["resources"])

    def test_project_sink(self):
        """Project sink resource exists."""
        self.assertIn("google_logging_project_sink.project_sink", self.parsed["resources"])

    def test_folder_sink(self):
        """Folder sink resource exists."""
        self.assertIn("google_logging_folder_sink.folder_sink", self.parsed["resources"])

    def test_organization_sink(self):
        """Organization sink resource exists."""
        self.assertIn("google_logging_organization_sink.org_sink", self.parsed["resources"])

    def test_log_bucket_config(self):
        """Log bucket config resources exist."""
        self.assertIn("google_logging_project_bucket_config.bucket", self.parsed["resources"])
        self.assertIn("google_logging_folder_bucket_config.folder_bucket", self.parsed["resources"])
        self.assertIn("google_logging_organization_bucket_config.org_bucket", self.parsed["resources"])

    def test_log_view(self):
        """Log view resource exists."""
        self.assertIn("google_logging_log_view.view", self.parsed["resources"])

    def test_target_type_validation(self):
        """Target type has validation."""
        tt = self.parsed["variables"].get("target_type", {})
        self.assertIn("validation", tt)
        self.assertIn("project", tt["validation"]["condition"])
        self.assertIn("folder", tt["validation"]["condition"])
        self.assertIn("organization", tt["validation"]["condition"])

    def test_audit_outputs(self):
        """Audit outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("audit_config_id", outputs)
        self.assertIn("sink_id", outputs)
        self.assertIn("sink_writer_identity", outputs)
        self.assertIn("log_bucket_id", outputs)
        self.assertIn("log_view_ids", outputs)

    def test_google_provider(self):
        """Google provider is declared."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("google", providers)
        self.assertEqual(providers["google"]["source"], "hashicorp/google")

    def test_exempted_members_support(self):
        """Exempted members are supported."""
        self.assertIn("exempted_members", self.parsed["variables"])

    def test_sink_exclusions_support(self):
        """Sink exclusions are supported."""
        self.assertIn("sink_exclusions", self.parsed["variables"])


class TestGCPOrganizationPoliciesModule(unittest.TestCase):
    """Tests for the GCP Organization Policies module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "gcp-compliance", "organization-policies")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Organization Policies module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_disable_serial_port_policy(self):
        """Disable serial port policy exists."""
        self.assertIn("google_org_policy_policy.disable_serial_port", self.parsed["resources"])

    def test_require_os_login_policy(self):
        """Require OS Login policy exists."""
        self.assertIn("google_org_policy_policy.require_os_login", self.parsed["resources"])

    def test_restrict_vm_external_ips_policy(self):
        """Restrict VM external IPs policy exists."""
        self.assertIn("google_org_policy_policy.restrict_vm_external_ips", self.parsed["resources"])

    def test_uniform_bucket_level_access_policy(self):
        """Uniform bucket level access policy exists."""
        self.assertIn("google_org_policy_policy.uniform_bucket_level_access", self.parsed["resources"])

    def test_restrict_public_ip_cloudsql_policy(self):
        """Restrict public IP Cloud SQL policy exists."""
        self.assertIn("google_org_policy_policy.restrict_public_ip_cloudsql", self.parsed["resources"])

    def test_disable_sa_key_creation_policy(self):
        """Disable SA key creation policy exists."""
        self.assertIn("google_org_policy_policy.disable_sa_key_creation", self.parsed["resources"])

    def test_disable_sa_key_upload_policy(self):
        """Disable SA key upload policy exists."""
        self.assertIn("google_org_policy_policy.disable_sa_key_upload", self.parsed["resources"])

    def test_require_vpc_flow_logs_policy(self):
        """Require VPC flow logs policy exists."""
        self.assertIn("google_org_policy_policy.require_vpc_flow_logs", self.parsed["resources"])

    def test_restrict_vpc_peering_policy(self):
        """Restrict VPC peering policy exists."""
        self.assertIn("google_org_policy_policy.restrict_vpc_peering", self.parsed["resources"])

    def test_disable_default_network_policy(self):
        """Disable default network policy exists."""
        self.assertIn("google_org_policy_policy.disable_default_network", self.parsed["resources"])

    def test_require_shielded_vms_policy(self):
        """Require Shielded VMs policy exists."""
        self.assertIn("google_org_policy_policy.require_shielded_vms", self.parsed["resources"])

    def test_custom_constraint_resource(self):
        """Custom constraint resource exists."""
        self.assertIn("google_org_policy_custom_constraint.custom", self.parsed["resources"])

    def test_custom_policy_resource(self):
        """Custom policy resource exists."""
        self.assertIn("google_org_policy_policy.custom", self.parsed["resources"])

    def test_policies_output(self):
        """Policies output is defined."""
        self.assertIn("enabled_policies", self.parsed["outputs"])

    def test_project_id_variable(self):
        """Project ID variable exists."""
        self.assertIn("project_id", self.parsed["variables"])

    def test_custom_constraints_variable(self):
        """Custom constraints variable exists."""
        self.assertIn("custom_constraints", self.parsed["variables"])

    def test_policy_count(self):
        """At least 15 organization policies are defined."""
        policy_count = sum(1 for k in self.parsed["resources"] if k.startswith("google_org_policy_policy."))
        self.assertGreaterEqual(policy_count, 15)


class TestGCPSecurityCommandCenterModule(unittest.TestCase):
    """Tests for the GCP Security Command Center module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "gcp-compliance", "security-command-center")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Security Command Center module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_scc_source_resource(self):
        """SCC source resource exists."""
        self.assertIn("google_scc_source.this", self.parsed["resources"])

    def test_notification_config_resource(self):
        """Notification config resource exists."""
        self.assertIn("google_scc_notification_config.this", self.parsed["resources"])

    def test_pubsub_topic_resource(self):
        """Pub/Sub topic resource exists."""
        self.assertIn("google_pubsub_topic.scc_notifications", self.parsed["resources"])

    def test_mute_config_resource(self):
        """Mute config resource exists."""
        self.assertIn("google_scc_mute_config.mute_rules", self.parsed["resources"])

    def test_custom_config_resource(self):
        """Custom config resource exists."""
        self.assertIn("google_scc_custom_config.this", self.parsed["resources"])

    def test_organization_id_validation(self):
        """Organization ID has validation."""
        oid = self.parsed["variables"].get("organization_id", {})
        self.assertIn("validation", oid)
        self.assertIn("regex", oid["validation"]["condition"])

    def test_scc_outputs(self):
        """SCC outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("source_id", outputs)
        self.assertIn("source_name", outputs)
        self.assertIn("notification_config_id", outputs)
        self.assertIn("pubsub_topic_id", outputs)
        self.assertIn("mute_config_ids", outputs)

    def test_mute_rules_for_each(self):
        """Mute rules use for_each."""
        resource = self.parsed["resources"]["google_scc_mute_config.mute_rules"]
        self.assertTrue(resource.get("for_each"))


class TestGCPVPCServiceControlsModule(unittest.TestCase):
    """Tests for the GCP VPC Service Controls module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "gcp-compliance", "vpc-service-controls")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """VPC Service Controls module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_access_policy_resource(self):
        """Access policy resource exists."""
        self.assertIn("google_access_context_manager_access_policy.this", self.parsed["resources"])

    def test_service_perimeter_resource(self):
        """Service perimeter resource exists."""
        self.assertIn("google_access_context_manager_service_perimeter.this", self.parsed["resources"])

    def test_access_level_resource(self):
        """Access level resource exists."""
        self.assertIn("google_access_context_manager_access_level.this", self.parsed["resources"])

    def test_ingress_policy_resource(self):
        """Ingress policy resource exists."""
        self.assertIn("google_access_context_manager_ingress_policy.this", self.parsed["resources"])

    def test_egress_policy_resource(self):
        """Egress policy resource exists."""
        self.assertIn("google_access_context_manager_egress_policy.this", self.parsed["resources"])

    def test_dry_run_perimeter(self):
        """Dry run perimeter resource exists."""
        self.assertIn("google_access_context_manager_service_perimeter.dry_run", self.parsed["resources"])

    def test_organization_id_validation(self):
        """Organization ID has validation."""
        oid = self.parsed["variables"].get("organization_id", {})
        self.assertIn("validation", oid)

    def test_vpc_outputs(self):
        """VPC outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("access_policy_id", outputs)
        self.assertIn("access_policy_name", outputs)
        self.assertIn("service_perimeter_id", outputs)
        self.assertIn("service_perimeter_name", outputs)
        self.assertIn("access_level_ids", outputs)
        self.assertIn("ingress_policy_ids", outputs)
        self.assertIn("egress_policy_ids", outputs)

    def test_restricted_services_default(self):
        """Restricted services have defaults."""
        rs = self.parsed["variables"].get("restricted_services", {})
        self.assertIn("default", rs)

    def test_vpc_accessible_services_default(self):
        """VPC accessible services have defaults."""
        vas = self.parsed["variables"].get("vpc_accessible_services", {})
        self.assertIn("default", vas)

    def test_access_levels_for_each(self):
        """Access levels use for_each."""
        resource = self.parsed["resources"]["google_access_context_manager_access_level.this"]
        self.assertTrue(resource.get("for_each"))

    def test_ingress_policies_for_each(self):
        """Ingress policies use for_each."""
        resource = self.parsed["resources"]["google_access_context_manager_ingress_policy.this"]
        self.assertTrue(resource.get("for_each"))

    def test_egress_policies_for_each(self):
        """Egress policies use for_each."""
        resource = self.parsed["resources"]["google_access_context_manager_egress_policy.this"]
        self.assertTrue(resource.get("for_each"))


if __name__ == "__main__":
    unittest.main()
