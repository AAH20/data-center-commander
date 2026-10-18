"""
Integration Module Tests
=========================
Tests for integration modules: Containerization, Data Center Ops, Virtualization.
"""

import os
import re
import unittest
from pathlib import Path

from tests.terraform.terraform_parser import TerraformParser, get_module_path


MODULES_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "terraform", "modules"))


class TestContainerizationModule(unittest.TestCase):
    """Tests for the Containerization module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "integration", "containerization")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Containerization module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_docker_network_resource(self):
        """Docker network resource exists."""
        self.assertIn("docker_network.data_center", self.parsed["resources"])

    def test_registry_image_resource(self):
        """Docker registry image resource exists."""
        self.assertIn("docker_registry_image.services", self.parsed["resources"])

    def test_container_resource(self):
        """Docker container resource exists."""
        self.assertIn("docker_container.services", self.parsed["resources"])

    def test_traefik_resource(self):
        """Traefik container resource exists."""
        self.assertIn("docker_container.traefik", self.parsed["resources"])

    def test_prometheus_resource(self):
        """Prometheus container resource exists."""
        self.assertIn("docker_container.prometheus", self.parsed["resources"])

    def test_grafana_resource(self):
        """Grafana container resource exists."""
        self.assertIn("docker_container.grafana", self.parsed["resources"])

    def test_environment_validation(self):
        """Environment has validation."""
        env = self.parsed["variables"].get("environment", {})
        self.assertIn("validation", env)
        self.assertIn("dev", env["validation"]["condition"])
        self.assertIn("staging", env["validation"]["condition"])
        self.assertIn("prod", env["validation"]["condition"])

    def test_services_variable(self):
        """Services variable exists."""
        self.assertIn("services", self.parsed["variables"])

    def test_enable_traefik_default(self):
        """Traefik defaults to enabled."""
        tr = self.parsed["variables"].get("enable_traefik", {})
        self.assertEqual(tr.get("default"), "true")

    def test_enable_monitoring_default(self):
        """Monitoring defaults to enabled."""
        mon = self.parsed["variables"].get("enable_monitoring", {})
        self.assertEqual(mon.get("default"), "true")

    def test_grafana_admin_password_sensitive(self):
        """Grafana admin password is sensitive."""
        pw = self.parsed["variables"].get("grafana_admin_password", {})
        self.assertTrue(pw.get("sensitive"))

    def test_containerization_outputs(self):
        """Containerization outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("network_id", outputs)
        self.assertIn("network_name", outputs)
        self.assertIn("service_container_ids", outputs)
        self.assertIn("service_container_names", outputs)
        self.assertIn("traefik_container_id", outputs)
        self.assertIn("prometheus_container_id", outputs)
        self.assertIn("grafana_container_id", outputs)

    def test_docker_provider(self):
        """Docker provider is declared."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("docker", providers)
        self.assertEqual(providers["docker"]["source"], "kreuzwerker/docker")

    def test_labels_support(self):
        """Labels are supported."""
        self.assertIn("labels", self.parsed["variables"])


class TestDataCenterOpsModule(unittest.TestCase):
    """Tests for the Data Center Ops module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "integration", "data-center-ops")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Data Center Ops module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_dc_config_resource(self):
        """Data center config resource exists."""
        self.assertIn("local_file.dc_config", self.parsed["resources"])

    def test_capacity_plan_resource(self):
        """Capacity plan resource exists."""
        self.assertIn("local_file.capacity_plan", self.parsed["resources"])

    def test_alert_rules_resource(self):
        """Alert rules resource exists."""
        self.assertIn("local_file.alert_rules", self.parsed["resources"])

    def test_backup_script_resource(self):
        """Backup script resource exists."""
        self.assertIn("local_file.backup_script", self.parsed["resources"])

    def test_runbook_resource(self):
        """Runbook resource exists."""
        self.assertIn("local_file.runbook", self.parsed["resources"])

    def test_environment_validation(self):
        """Environment has validation."""
        env = self.parsed["variables"].get("environment", {})
        self.assertIn("validation", env)

    def test_tier_validation(self):
        """Tier has validation."""
        tier = self.parsed["variables"].get("tier", {})
        self.assertIn("validation", tier)
        self.assertIn("I", tier["validation"]["condition"])
        self.assertIn("II", tier["validation"]["condition"])
        self.assertIn("III", tier["validation"]["condition"])
        self.assertIn("IV", tier["validation"]["condition"])

    def test_capacity_variables(self):
        """Capacity variables exist."""
        self.assertIn("total_racks", self.parsed["variables"])
        self.assertIn("rack_units", self.parsed["variables"])
        self.assertIn("total_power_kw", self.parsed["variables"])
        self.assertIn("total_cooling_tons", self.parsed["variables"])
        self.assertIn("total_network_gbps", self.parsed["variables"])
        self.assertIn("usable_floor_sqm", self.parsed["variables"])

    def test_threshold_variables(self):
        """Threshold variables exist."""
        self.assertIn("pue_warning_threshold", self.parsed["variables"])
        self.assertIn("pue_critical_threshold", self.parsed["variables"])
        self.assertIn("temp_warning_c", self.parsed["variables"])
        self.assertIn("temp_critical_c", self.parsed["variables"])
        self.assertIn("humidity_warning_pct", self.parsed["variables"])
        self.assertIn("humidity_critical_pct", self.parsed["variables"])

    def test_monitoring_variables(self):
        """Monitoring variables exist."""
        self.assertIn("prometheus_enabled", self.parsed["variables"])
        self.assertIn("grafana_enabled", self.parsed["variables"])
        self.assertIn("alertmanager_enabled", self.parsed["variables"])
        self.assertIn("scrape_interval", self.parsed["variables"])
        self.assertIn("retention_days", self.parsed["variables"])

    def test_backup_variables(self):
        """Backup variables exist."""
        self.assertIn("backup_enabled", self.parsed["variables"])
        self.assertIn("backup_schedule", self.parsed["variables"])
        self.assertIn("backup_retention_count", self.parsed["variables"])
        self.assertIn("offsite_replication", self.parsed["variables"])

    def test_security_variables(self):
        """Security variables exist."""
        self.assertIn("tls_enabled", self.parsed["variables"])
        self.assertIn("cert_manager_enabled", self.parsed["variables"])
        self.assertIn("network_policies_enabled", self.parsed["variables"])
        self.assertIn("audit_logging_enabled", self.parsed["variables"])

    def test_contact_variables(self):
        """Contact variables exist."""
        self.assertIn("facilities_contact", self.parsed["variables"])
        self.assertIn("noc_contact", self.parsed["variables"])
        self.assertIn("security_contact", self.parsed["variables"])

    def test_dc_ops_outputs(self):
        """Data Center Ops outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("config_file_path", outputs)
        self.assertIn("capacity_plan_path", outputs)
        self.assertIn("alert_rules_path", outputs)
        self.assertIn("backup_script_path", outputs)
        self.assertIn("runbook_path", outputs)
        self.assertIn("datacenter_name", outputs)
        self.assertIn("environment", outputs)
        self.assertIn("tier", outputs)
        self.assertIn("total_capacity", outputs)
        self.assertIn("utilization", outputs)

    def test_null_and_local_providers(self):
        """Null and local providers are declared."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("null", providers)
        self.assertIn("local", providers)

    def test_prometheus_enabled_default(self):
        """Prometheus defaults to enabled."""
        pe = self.parsed["variables"].get("prometheus_enabled", {})
        self.assertEqual(pe.get("default"), "true")

    def test_backup_enabled_default(self):
        """Backup defaults to enabled."""
        be = self.parsed["variables"].get("backup_enabled", {})
        self.assertEqual(be.get("default"), "true")

    def test_tls_enabled_default(self):
        """TLS defaults to enabled."""
        tls = self.parsed["variables"].get("tls_enabled", {})
        self.assertEqual(tls.get("default"), "true")


class TestVirtualizationModule(unittest.TestCase):
    """Tests for the Virtualization module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "integration", "virtualization")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Virtualization module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_pool_resource(self):
        """Libvirt pool resource exists."""
        self.assertIn("libvirt_pool.data_center", self.parsed["resources"])

    def test_network_resource(self):
        """Libvirt network resource exists."""
        self.assertIn("libvirt_network.data_center", self.parsed["resources"])

    def test_base_volume_resource(self):
        """Base volume resource exists."""
        self.assertIn("libvirt_volume.base", self.parsed["resources"])

    def test_vm_volume_resource(self):
        """VM volume resource exists."""
        self.assertIn("libvirt_volume.vm", self.parsed["resources"])

    def test_cloudinit_disk_resource(self):
        """Cloud-init disk resource exists."""
        self.assertIn("libvirt_cloudinit_disk.vm", self.parsed["resources"])

    def test_domain_resource(self):
        """Libvirt domain resource exists."""
        self.assertIn("libvirt_domain.vm", self.parsed["resources"])

    def test_environment_validation(self):
        """Environment has validation."""
        env = self.parsed["variables"].get("environment", {})
        self.assertIn("validation", env)

    def test_vm_count_validation(self):
        """VM count has validation."""
        vc = self.parsed["variables"].get("vm_count", {})
        self.assertIn("validation", vc)
        self.assertIn("vm_count > 0", vc["validation"]["condition"])
        self.assertIn("vm_count <= 20", vc["validation"]["condition"])

    def test_virtualization_outputs(self):
        """Virtualization outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("pool_name", outputs)
        self.assertIn("network_id", outputs)
        self.assertIn("network_name", outputs)
        self.assertIn("vm_names", outputs)
        self.assertIn("vm_ips", outputs)
        self.assertIn("vm_ids", outputs)
        self.assertIn("base_volume_id", outputs)

    def test_libvirt_provider(self):
        """Libvirt provider is declared."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("libvirt", providers)
        self.assertEqual(providers["libvirt"]["source"], "dmacvicar/libvirt")

    def test_ssh_public_key_support(self):
        """SSH public key is supported."""
        self.assertIn("ssh_public_key", self.parsed["variables"])

    def test_base_image_path_required(self):
        """Base image path is required."""
        self.assertIn("base_image_path", self.parsed["variables"])


if __name__ == "__main__":
    unittest.main()
