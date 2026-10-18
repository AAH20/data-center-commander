"""
DigitalOcean Module Tests
=========================
Tests for DigitalOcean modules: Droplets, VPC, Load Balancer, Block Storage, Database, Monitoring.
"""

import os
import re
import unittest
from pathlib import Path

from tests.terraform.terraform_parser import TerraformParser, get_module_path


MODULES_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "iac", "modules"))


class TestDigitalOceanDropletsModule(unittest.TestCase):
    """Tests for the DigitalOcean Droplets module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "digitalocean", "droplets")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Droplets module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_droplet_resource(self):
        """Droplet resource exists."""
        self.assertIn("digitalocean_droplet.this", self.parsed["resources"])

    def test_count_validation(self):
        """Count has validation."""
        count = self.parsed["variables"].get("count", {})
        self.assertIn("validation", count)
        self.assertIn("count > 0", count["validation"]["condition"])

    def test_region_variable(self):
        """Region variable exists."""
        self.assertIn("region", self.parsed["variables"])

    def test_size_variable(self):
        """Size variable exists."""
        self.assertIn("size", self.parsed["variables"])

    def test_image_variable(self):
        """Image variable exists."""
        self.assertIn("image", self.parsed["variables"])

    def test_ssh_keys_support(self):
        """SSH keys are supported."""
        self.assertIn("ssh_keys", self.parsed["variables"])

    def test_backups_support(self):
        """Backups are supported."""
        self.assertIn("backups", self.parsed["variables"])

    def test_monitoring_default(self):
        """Monitoring defaults to true."""
        mon = self.parsed["variables"].get("monitoring", {})
        self.assertEqual(mon.get("default"), "true")

    def test_ipv6_support(self):
        """IPv6 is supported."""
        self.assertIn("ipv6", self.parsed["variables"])

    def test_user_data_support(self):
        """User data is supported."""
        self.assertIn("user_data", self.parsed["variables"])

    def test_graceful_shutdown_support(self):
        """Graceful shutdown is supported."""
        self.assertIn("graceful_shutdown", self.parsed["variables"])

    def test_prevent_destroy_support(self):
        """Prevent destroy is supported."""
        self.assertIn("prevent_destroy", self.parsed["variables"])

    def test_droplet_outputs(self):
        """Droplet outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("droplet_ids", outputs)
        self.assertIn("droplet_urns", outputs)
        self.assertIn("droplet_names", outputs)
        self.assertIn("droplet_ipv4_addresses", outputs)
        self.assertIn("droplet_ipv4_addresses_private", outputs)
        self.assertIn("droplet_ipv6_addresses", outputs)
        self.assertIn("droplet_regions", outputs)
        self.assertIn("droplet_sizes", outputs)
        self.assertIn("droplet_tags", outputs)

    def test_digitalocean_provider(self):
        """DigitalOcean provider is declared."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("digitalocean", providers)
        self.assertEqual(providers["digitalocean"]["source"], "digitalocean/digitalocean")


class TestDigitalOceanVPCModule(unittest.TestCase):
    """Tests for the DigitalOcean VPC module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "digitalocean", "vpc")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """VPC module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_vpc_resource(self):
        """VPC resource exists."""
        self.assertIn("digitalocean_vpc.this", self.parsed["resources"])

    def test_ip_range_validation(self):
        """IP range has CIDR validation."""
        ip = self.parsed["variables"].get("ip_range", {})
        self.assertIn("validation", ip)
        self.assertIn("cidrnetmask", ip["validation"]["condition"])

    def test_region_validation(self):
        """Region has validation."""
        reg = self.parsed["variables"].get("region", {})
        self.assertIn("validation", reg)

    def test_vpc_outputs(self):
        """VPC outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("vpc_id", outputs)
        self.assertIn("vpc_urn", outputs)
        self.assertIn("vpc_ip_range", outputs)
        self.assertIn("vpc_default", outputs)


class TestDigitalOceanLoadBalancerModule(unittest.TestCase):
    """Tests for the DigitalOcean Load Balancer module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "digitalocean", "load-balancer")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Load Balancer module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_loadbalancer_resource(self):
        """Load balancer resource exists."""
        self.assertIn("digitalocean_loadbalancer.this", self.parsed["resources"])

    def test_size_validation(self):
        """Size has validation."""
        size = self.parsed["variables"].get("size", {})
        self.assertIn("validation", size)
        self.assertIn("lb-small", size["validation"]["condition"])
        self.assertIn("lb-medium", size["validation"]["condition"])
        self.assertIn("lb-large", size["validation"]["condition"])

    def test_algorithm_validation(self):
        """Algorithm has validation."""
        algo = self.parsed["variables"].get("algorithm", {})
        self.assertIn("validation", algo)
        self.assertIn("round_robin", algo["validation"]["condition"])
        self.assertIn("least_connections", algo["validation"]["condition"])

    def test_forwarding_rules(self):
        """Forwarding rules are supported."""
        self.assertIn("forwarding_rules", self.parsed["variables"])

    def test_healthcheck_support(self):
        """Healthcheck is supported."""
        self.assertIn("healthcheck", self.parsed["variables"])

    def test_sticky_sessions_support(self):
        """Sticky sessions are supported."""
        self.assertIn("sticky_sessions", self.parsed["variables"])

    def test_redirect_http_to_https(self):
        """HTTP to HTTPS redirect is supported."""
        self.assertIn("redirect_http_to_https", self.parsed["variables"])

    def test_proxy_protocol_support(self):
        """Proxy protocol is supported."""
        self.assertIn("enable_proxy_protocol", self.parsed["variables"])

    def test_backend_keepalive_support(self):
        """Backend keepalive is supported."""
        self.assertIn("enable_backend_keepalive", self.parsed["variables"])

    def test_prevent_destroy_support(self):
        """Prevent destroy is supported."""
        self.assertIn("prevent_destroy", self.parsed["variables"])

    def test_loadbalancer_outputs(self):
        """Load balancer outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("loadbalancer_id", outputs)
        self.assertIn("loadbalancer_urn", outputs)
        self.assertIn("loadbalancer_ip", outputs)
        self.assertIn("loadbalancer_name", outputs)
        self.assertIn("loadbalancer_region", outputs)
        self.assertIn("loadbalancer_size", outputs)
        self.assertIn("loadbalancer_algorithm", outputs)
        self.assertIn("loadbalancer_status", outputs)
        self.assertIn("loadbalancer_forwarding_rules", outputs)
        self.assertIn("loadbalancer_healthcheck", outputs)
        self.assertIn("loadbalancer_sticky_sessions", outputs)
        self.assertIn("loadbalancer_droplet_ids", outputs)

    def test_dynamic_forwarding_rule(self):
        """Dynamic forwarding rule block is used."""
        resource = self.parsed["resources"]["digitalocean_loadbalancer.this"]
        self.assertTrue(resource.get("dynamic"))

    def test_dynamic_healthcheck(self):
        """Dynamic healthcheck block is used."""
        resource = self.parsed["resources"]["digitalocean_loadbalancer.this"]
        self.assertTrue(resource.get("dynamic"))


class TestDigitalOceanBlockStorageModule(unittest.TestCase):
    """Tests for the DigitalOcean Block Storage module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "digitalocean", "block-storage")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Block Storage module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_volume_resource(self):
        """Volume resource exists."""
        self.assertIn("digitalocean_volume.this", self.parsed["resources"])

    def test_volume_attachment_resource(self):
        """Volume attachment resource exists."""
        self.assertIn("digitalocean_volume_attachment.this", self.parsed["resources"])

    def test_count_validation(self):
        """Count has validation."""
        count = self.parsed["variables"].get("count", {})
        self.assertIn("validation", count)

    def test_size_validation(self):
        """Size has validation."""
        size = self.parsed["variables"].get("size", {})
        self.assertIn("validation", size)
        self.assertIn("size >= 1", size["validation"]["condition"])

    def test_filesystem_type_validation(self):
        """Filesystem type has validation."""
        fs = self.parsed["variables"].get("filesystem_type", {})
        self.assertIn("validation", fs)
        self.assertIn("ext4", fs["validation"]["condition"])
        self.assertIn("xfs", fs["validation"]["condition"])

    def test_attach_to_droplets(self):
        """Attach to droplets is supported."""
        self.assertIn("attach_to_droplets", self.parsed["variables"])

    def test_prevent_destroy_support(self):
        """Prevent destroy is supported."""
        self.assertIn("prevent_destroy", self.parsed["variables"])

    def test_volume_outputs(self):
        """Volume outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("volume_ids", outputs)
        self.assertIn("volume_urns", outputs)
        self.assertIn("volume_names", outputs)
        self.assertIn("volume_regions", outputs)
        self.assertIn("volume_sizes", outputs)
        self.assertIn("volume_filesystem_types", outputs)
        self.assertIn("volume_filesystem_labels", outputs)
        self.assertIn("volume_droplet_ids", outputs)
        self.assertIn("volume_descriptions", outputs)
        self.assertIn("volume_tags", outputs)
        self.assertIn("attachment_ids", outputs)


class TestDigitalOceanDatabaseModule(unittest.TestCase):
    """Tests for the DigitalOcean Database module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "digitalocean", "database")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Database module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_database_cluster_resource(self):
        """Database cluster resource exists."""
        self.assertIn("digitalocean_database_cluster.this", self.parsed["resources"])

    def test_database_db_resource(self):
        """Database DB resource exists."""
        self.assertIn("digitalocean_database_db.this", self.parsed["resources"])

    def test_database_user_resource(self):
        """Database user resource exists."""
        self.assertIn("digitalocean_database_user.this", self.parsed["resources"])

    def test_database_firewall_resource(self):
        """Database firewall resource exists."""
        self.assertIn("digitalocean_database_firewall.this", self.parsed["resources"])

    def test_engine_validation(self):
        """Engine has validation."""
        engine = self.parsed["variables"].get("engine", {})
        self.assertIn("validation", engine)
        self.assertIn("pg", engine["validation"]["condition"])
        self.assertIn("mysql", engine["validation"]["condition"])
        self.assertIn("redis", engine["validation"]["condition"])
        self.assertIn("mongodb", engine["validation"]["condition"])

    def test_node_count_validation(self):
        """Node count has validation."""
        nc = self.parsed["variables"].get("node_count", {})
        self.assertIn("validation", nc)

    def test_maintenance_window(self):
        """Maintenance window is supported."""
        self.assertIn("maintenance_day", self.parsed["variables"])
        self.assertIn("maintenance_hour", self.parsed["variables"])

    def test_private_network_support(self):
        """Private network is supported."""
        self.assertIn("private_network_uuid", self.parsed["variables"])

    def test_prevent_destroy_support(self):
        """Prevent destroy is supported."""
        self.assertIn("prevent_destroy", self.parsed["variables"])

    def test_database_outputs(self):
        """Database outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("database_cluster_id", outputs)
        self.assertIn("database_cluster_urn", outputs)
        self.assertIn("database_cluster_name", outputs)
        self.assertIn("database_cluster_engine", outputs)
        self.assertIn("database_cluster_version", outputs)
        self.assertIn("database_cluster_size", outputs)
        self.assertIn("database_cluster_region", outputs)
        self.assertIn("database_cluster_host", outputs)
        self.assertIn("database_cluster_port", outputs)
        self.assertIn("database_cluster_uri", outputs)
        self.assertIn("database_cluster_private_uri", outputs)
        self.assertIn("database_cluster_status", outputs)
        self.assertIn("database_cluster_maintenance_window", outputs)
        self.assertIn("database_cluster_node_count", outputs)
        self.assertIn("database_db_ids", outputs)
        self.assertIn("database_user_ids", outputs)
        self.assertIn("database_firewall_id", outputs)

    def test_sensitive_outputs(self):
        """Sensitive outputs are marked."""
        uri = self.parsed["outputs"].get("database_cluster_uri", {})
        self.assertTrue(uri.get("sensitive"))
        private_uri = self.parsed["outputs"].get("database_cluster_private_uri", {})
        self.assertTrue(private_uri.get("sensitive"))
        password = self.parsed["outputs"].get("database_cluster_password", {})
        self.assertTrue(password.get("sensitive"))


class TestDigitalOceanMonitoringModule(unittest.TestCase):
    """Tests for the DigitalOcean Monitoring module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "digitalocean", "monitoring")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Monitoring module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_monitor_alert_resource(self):
        """Monitor alert resource exists."""
        self.assertIn("digitalocean_monitor_alert.this", self.parsed["resources"])

    def test_alerts_variable(self):
        """Alerts variable exists."""
        self.assertIn("alerts", self.parsed["variables"])

    def test_alert_for_each(self):
        """Alerts use for_each."""
        resource = self.parsed["resources"]["digitalocean_monitor_alert.this"]
        self.assertTrue(resource.get("for_each"))

    def test_monitoring_outputs(self):
        """Monitoring outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("alert_ids", outputs)
        self.assertIn("alert_types", outputs)
        self.assertIn("alert_descriptions", outputs)
        self.assertIn("alert_enabled", outputs)
        self.assertIn("alert_entities", outputs)


if __name__ == "__main__":
    unittest.main()
