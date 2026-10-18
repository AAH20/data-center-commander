"""
GCP Core Module Tests
=====================
Tests for GCP infrastructure modules: VPC, Subnets, Firewall, GCE, Cloud SQL, GCS, Monitoring, IAM.
"""

import os
import re
import unittest
from pathlib import Path

from tests.terraform.terraform_parser import TerraformParser, get_module_path, read_tf_file


MODULES_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "iac", "modules"))
TERRAFORM_MODULES_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "terraform", "modules"))


class TestGCPVPCModule(unittest.TestCase):
    """Tests for the GCP VPC module (network/gcp)."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "network", "gcp")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """VPC module directory exists with required files."""
        self.assertTrue(os.path.isdir(self.module_path))
        for f in ["main.tf", "variables.tf", "outputs.tf"]:
            self.assertTrue(os.path.exists(os.path.join(self.module_path, f)))

    def test_required_version(self):
        """Terraform version constraint is set."""
        self.assertIn("required_version", self.parsed["terraform_config"])
        version = self.parsed["terraform_config"]["required_version"]
        self.assertRegex(version, r">=\s*\d+\.\d+")

    def test_google_provider_declared(self):
        """Google provider is declared with correct source."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("google", providers)
        self.assertEqual(providers["google"]["source"], "hashicorp/google")

    def test_vpc_network_resource(self):
        """VPC network resource is defined."""
        self.assertIn("google_compute_network.this", self.parsed["resources"])

    def test_vpc_auto_create_subnetworks_false(self):
        """VPC has auto_create_subnetworks disabled."""
        resource = self.parsed["resources"]["google_compute_network.this"]
        body = resource.get("body", "")
        self.assertIn("auto_create_subnetworks", body)
        self.assertIn("false", body)

    def test_vpc_routing_mode(self):
        """VPC has routing mode set."""
        resource = self.parsed["resources"]["google_compute_network.this"]
        body = resource.get("body", "")
        self.assertIn("routing_mode", body)
        self.assertIn("REGIONAL", body)

    def test_vpc_labels(self):
        """VPC has labels."""
        resource = self.parsed["resources"]["google_compute_network.this"]
        body = resource.get("body", "")
        self.assertIn("labels", body)

    def test_network_name_variable(self):
        """Network name variable exists."""
        self.assertIn("network_name", self.parsed["variables"])

    def test_project_id_variable(self):
        """Project ID variable exists."""
        self.assertIn("project_id", self.parsed["variables"])

    def test_region_variable_default(self):
        """Region variable has default."""
        region = self.parsed["variables"].get("region", {})
        self.assertIn("default", region)
        # Parser may include quotes around string defaults
        default_val = region["default"].strip('"')
        self.assertEqual(default_val, "us-central1")

    def test_vpc_cidr_variable(self):
        """VPC CIDR variable exists."""
        self.assertIn("vpc_cidr", self.parsed["variables"])

    def test_subnet_cidr_variable(self):
        """Subnet CIDR variable exists."""
        self.assertIn("subnet_cidr", self.parsed["variables"])

    def test_network_outputs(self):
        """Network outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("network_id", outputs)
        self.assertIn("network_name", outputs)
        self.assertIn("network_self_link", outputs)


class TestGCPSubnetsModule(unittest.TestCase):
    """Tests for the GCP Subnets module (network/gcp)."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "network", "gcp")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_subnet_resource(self):
        """Subnetwork resource is defined."""
        self.assertIn("google_compute_subnetwork.this", self.parsed["resources"])

    def test_subnet_ip_cidr_range(self):
        """Subnet has IP CIDR range."""
        resource = self.parsed["resources"]["google_compute_subnetwork.this"]
        body = resource.get("body", "")
        self.assertIn("ip_cidr_range", body)

    def test_subnet_private_ip_google_access(self):
        """Subnet has private Google access enabled."""
        resource = self.parsed["resources"]["google_compute_subnetwork.this"]
        body = resource.get("body", "")
        self.assertIn("private_ip_google_access", body)
        self.assertIn("true", body)

    def test_subnet_log_config(self):
        """Subnet has log config for flow logs."""
        resource = self.parsed["resources"]["google_compute_subnetwork.this"]
        body = resource.get("body", "")
        self.assertIn("log_config", body)
        self.assertIn("aggregation_interval", body)
        self.assertIn("flow_sampling", body)

    def test_subnet_labels(self):
        """Subnet has labels."""
        resource = self.parsed["resources"]["google_compute_subnetwork.this"]
        body = resource.get("body", "")
        self.assertIn("labels", body)

    def test_subnet_outputs(self):
        """Subnet outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("subnet_id", outputs)
        self.assertIn("subnet_self_link", outputs)


class TestGCPFirewallModule(unittest.TestCase):
    """Tests for the GCP Firewall module (network/gcp)."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "network", "gcp")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_allow_internal_firewall(self):
        """Allow internal firewall rule exists."""
        self.assertIn("google_compute_firewall.allow_internal", self.parsed["resources"])

    def test_allow_internal_protocols(self):
        """Allow internal firewall allows TCP, UDP, ICMP."""
        resource = self.parsed["resources"]["google_compute_firewall.allow_internal"]
        body = resource.get("body", "")
        self.assertIn("tcp", body)
        self.assertIn("udp", body)
        self.assertIn("icmp", body)

    def test_allow_internal_source_ranges(self):
        """Allow internal firewall has source ranges."""
        resource = self.parsed["resources"]["google_compute_firewall.allow_internal"]
        body = resource.get("body", "")
        self.assertIn("source_ranges", body)

    def test_allow_ssh_firewall(self):
        """Allow SSH firewall rule exists."""
        self.assertIn("google_compute_firewall.allow_ssh", self.parsed["resources"])

    def test_allow_ssh_port(self):
        """Allow SSH firewall allows port 22."""
        resource = self.parsed["resources"]["google_compute_firewall.allow_ssh"]
        body = resource.get("body", "")
        self.assertIn("22", body)

    def test_allow_http_firewall(self):
        """Allow HTTP firewall rule exists."""
        self.assertIn("google_compute_firewall.allow_http", self.parsed["resources"])

    def test_allow_http_ports(self):
        """Allow HTTP firewall allows ports 80 and 443."""
        resource = self.parsed["resources"]["google_compute_firewall.allow_http"]
        body = resource.get("body", "")
        self.assertIn("80", body)
        self.assertIn("443", body)

    def test_firewall_direction_ingress(self):
        """Firewall rules have INGRESS direction."""
        for key in ["google_compute_firewall.allow_internal", "google_compute_firewall.allow_ssh", "google_compute_firewall.allow_http"]:
            resource = self.parsed["resources"][key]
            body = resource.get("body", "")
            self.assertIn("INGRESS", body)

    def test_firewall_labels(self):
        """Firewall rules have labels."""
        for key in ["google_compute_firewall.allow_internal", "google_compute_firewall.allow_ssh", "google_compute_firewall.allow_http"]:
            resource = self.parsed["resources"][key]
            body = resource.get("body", "")
            self.assertIn("labels", body)


class TestGCPRouterNATModule(unittest.TestCase):
    """Tests for the GCP Router and NAT module (network/gcp)."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "network", "gcp")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_router_resource(self):
        """Cloud Router resource exists."""
        self.assertIn("google_compute_router.this", self.parsed["resources"])

    def test_router_count(self):
        """Router uses count for conditional creation."""
        resource = self.parsed["resources"]["google_compute_router.this"]
        self.assertTrue(resource.get("count"))

    def test_nat_resource(self):
        """Cloud NAT resource exists."""
        self.assertIn("google_compute_router_nat.this", self.parsed["resources"])

    def test_nat_count(self):
        """NAT uses count for conditional creation."""
        resource = self.parsed["resources"]["google_compute_router_nat.this"]
        self.assertTrue(resource.get("count"))

    def test_nat_ip_allocate_option(self):
        """NAT has IP allocate option."""
        resource = self.parsed["resources"]["google_compute_router_nat.this"]
        body = resource.get("body", "")
        self.assertIn("nat_ip_allocate_option", body)
        self.assertIn("AUTO_ONLY", body)

    def test_enable_cloud_nat_variable(self):
        """Enable Cloud NAT variable exists."""
        self.assertIn("enable_cloud_nat", self.parsed["variables"])

    def test_enable_cloud_nat_default(self):
        """Enable Cloud NAT defaults to true."""
        nat = self.parsed["variables"].get("enable_cloud_nat", {})
        self.assertEqual(nat.get("default"), "true")

    def test_router_output(self):
        """Router output is defined."""
        self.assertIn("router_id", self.parsed["outputs"])

    def test_nat_output(self):
        """NAT output is defined."""
        self.assertIn("nat_id", self.parsed["outputs"])


class TestGCPGCEModule(unittest.TestCase):
    """Tests for the GCP GCE module (compute/gcp)."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "compute", "gcp")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """GCE module directory exists with required files."""
        self.assertTrue(os.path.isdir(self.module_path))
        for f in ["main.tf", "variables.tf", "outputs.tf"]:
            self.assertTrue(os.path.exists(os.path.join(self.module_path, f)))

    def test_required_version(self):
        """Terraform version constraint is set."""
        self.assertIn("required_version", self.parsed["terraform_config"])
        version = self.parsed["terraform_config"]["required_version"]
        self.assertRegex(version, r">=\s*\d+\.\d+")

    def test_google_provider_declared(self):
        """Google provider is declared with correct source."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("google", providers)
        self.assertEqual(providers["google"]["source"], "hashicorp/google")

    def test_instance_resource(self):
        """GCE instance resource is defined."""
        self.assertIn("google_compute_instance.this", self.parsed["resources"])

    def test_instance_count(self):
        """Instance uses count."""
        resource = self.parsed["resources"]["google_compute_instance.this"]
        self.assertTrue(resource.get("count"))

    def test_ubuntu_image_data_source(self):
        """Ubuntu image data source exists."""
        self.assertIn("google_compute_image.ubuntu", self.parsed["data_sources"])

    def test_boot_disk(self):
        """Boot disk is configured."""
        resource = self.parsed["resources"]["google_compute_instance.this"]
        body = resource.get("body", "")
        self.assertIn("boot_disk", body)
        self.assertIn("initialize_params", body)

    def test_boot_disk_size_variable(self):
        """Boot disk size variable exists."""
        self.assertIn("boot_disk_size", self.parsed["variables"])

    def test_boot_disk_size_default(self):
        """Boot disk size has default."""
        size = self.parsed["variables"].get("boot_disk_size", {})
        self.assertIn("default", size)

    def test_machine_type_variable(self):
        """Machine type variable exists."""
        self.assertIn("machine_type", self.parsed["variables"])

    def test_machine_type_default(self):
        """Machine type has default."""
        mt = self.parsed["variables"].get("machine_type", {})
        self.assertIn("default", mt)

    def test_instance_count_variable(self):
        """Instance count variable exists."""
        self.assertIn("instance_count", self.parsed["variables"])

    def test_instance_count_default(self):
        """Instance count defaults to 1."""
        count = self.parsed["variables"].get("instance_count", {})
        self.assertEqual(count.get("default"), "1")

    def test_zones_variable(self):
        """Zones variable exists."""
        self.assertIn("zones", self.parsed["variables"])

    def test_zones_default(self):
        """Zones have defaults."""
        zones = self.parsed["variables"].get("zones", {})
        self.assertIn("default", zones)

    def test_network_interface(self):
        """Network interface is configured."""
        resource = self.parsed["resources"]["google_compute_instance.this"]
        body = resource.get("body", "")
        self.assertIn("network_interface", body)

    def test_network_id_variable(self):
        """Network ID variable exists."""
        self.assertIn("network_id", self.parsed["variables"])

    def test_subnet_id_variable(self):
        """Subnet ID variable exists."""
        self.assertIn("subnet_id", self.parsed["variables"])

    def test_static_ip_resource(self):
        """Static IP address resource exists."""
        self.assertIn("google_compute_address.this", self.parsed["resources"])

    def test_static_ip_count(self):
        """Static IP uses count."""
        resource = self.parsed["resources"]["google_compute_address.this"]
        self.assertTrue(resource.get("count"))

    def test_enable_static_ip_variable(self):
        """Enable static IP variable exists."""
        self.assertIn("enable_static_ip", self.parsed["variables"])

    def test_enable_static_ip_default(self):
        """Enable static IP defaults to false."""
        sip = self.parsed["variables"].get("enable_static_ip", {})
        self.assertEqual(sip.get("default"), "false")

    def test_shielded_instance_config(self):
        """Shielded instance config is enabled."""
        resource = self.parsed["resources"]["google_compute_instance.this"]
        body = resource.get("body", "")
        self.assertIn("shielded_instance_config", body)
        self.assertIn("enable_secure_boot", body)
        self.assertIn("enable_vtpm", body)
        self.assertIn("enable_integrity_monitoring", body)

    def test_oslogin_metadata(self):
        """OS Login is enabled in metadata."""
        resource = self.parsed["resources"]["google_compute_instance.this"]
        body = resource.get("body", "")
        self.assertIn("enable-oslogin", body)
        self.assertIn("TRUE", body)

    def test_encryption_variable(self):
        """Encryption variable exists."""
        self.assertIn("enable_encryption", self.parsed["variables"])

    def test_encryption_default(self):
        """Encryption defaults to true."""
        enc = self.parsed["variables"].get("enable_encryption", {})
        self.assertEqual(enc.get("default"), "true")

    def test_kms_key_id_variable(self):
        """KMS key ID variable exists."""
        self.assertIn("kms_key_id", self.parsed["variables"])

    def test_monitoring_variable(self):
        """Monitoring variable exists."""
        self.assertIn("enable_monitoring", self.parsed["variables"])

    def test_monitoring_default(self):
        """Monitoring defaults to true."""
        mon = self.parsed["variables"].get("enable_monitoring", {})
        self.assertEqual(mon.get("default"), "true")

    def test_lifecycle_create_before_destroy(self):
        """Lifecycle create_before_destroy is set."""
        resource = self.parsed["resources"]["google_compute_instance.this"]
        self.assertTrue(resource.get("lifecycle"))

    def test_instance_outputs(self):
        """Instance outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("instance_ids", outputs)
        self.assertIn("instance_names", outputs)
        self.assertIn("instance_public_ips", outputs)
        self.assertIn("instance_private_ips", outputs)
        self.assertIn("instance_zones", outputs)

    def test_environment_variable(self):
        """Environment variable exists."""
        self.assertIn("environment", self.parsed["variables"])

    def test_common_tags_variable(self):
        """Common tags variable exists."""
        self.assertIn("common_tags", self.parsed["variables"])


class TestGCPCloudSQLModule(unittest.TestCase):
    """Tests for the GCP Cloud SQL module (terraform/modules/gcp/cloudsql)."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(TERRAFORM_MODULES_BASE)
        cls.module_path = get_module_path(TERRAFORM_MODULES_BASE, "gcp", "cloudsql")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Cloud SQL module directory exists with required files."""
        self.assertTrue(os.path.isdir(self.module_path))
        for f in ["main.tf", "variables.tf", "outputs.tf"]:
            self.assertTrue(os.path.exists(os.path.join(self.module_path, f)))

    def test_required_version(self):
        """Terraform version constraint is set."""
        self.assertIn("required_version", self.parsed["terraform_config"])
        version = self.parsed["terraform_config"]["required_version"]
        self.assertRegex(version, r">=\s*\d+\.\d+")

    def test_google_provider_declared(self):
        """Google provider is declared with correct source."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("google", providers)
        self.assertEqual(providers["google"]["source"], "hashicorp/google")

    def test_random_provider_declared(self):
        """Random provider is declared."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("random", providers)

    def test_sql_database_instance_resource(self):
        """Cloud SQL database instance resource is defined."""
        self.assertIn("google_sql_database_instance.this", self.parsed["resources"])

    def test_sql_database_resource(self):
        """Cloud SQL database resource is defined."""
        self.assertIn("google_sql_database.this", self.parsed["resources"])

    def test_random_password_resource(self):
        """Random password resource exists."""
        self.assertIn("random_password.master_password", self.parsed["resources"])

    def test_random_password_count(self):
        """Random password uses count."""
        resource = self.parsed["resources"]["random_password.master_password"]
        self.assertTrue(resource.get("count"))

    def test_backup_configuration(self):
        """Backup configuration exists."""
        resource = self.parsed["resources"]["google_sql_database_instance.this"]
        body = resource.get("body", "")
        self.assertIn("backup_configuration", body)
        self.assertIn("enabled", body)
        self.assertIn("start_time", body)
        self.assertIn("point_in_time_recovery_enabled", body)

    def test_disk_encryption_configuration(self):
        """Disk encryption configuration exists."""
        resource = self.parsed["resources"]["google_sql_database_instance.this"]
        body = resource.get("body", "")
        self.assertIn("disk_encryption_configuration", body)
        self.assertIn("kms_key_name", body)

    def test_maintenance_window(self):
        """Maintenance window exists."""
        resource = self.parsed["resources"]["google_sql_database_instance.this"]
        body = resource.get("body", "")
        self.assertIn("maintenance_window", body)
        self.assertIn("day", body)
        self.assertIn("hour", body)

    def test_ip_configuration(self):
        """IP configuration exists."""
        resource = self.parsed["resources"]["google_sql_database_instance.this"]
        body = resource.get("body", "")
        self.assertIn("ip_configuration", body)
        self.assertIn("ipv4_enabled", body)
        self.assertIn("require_ssl", body)

    def test_authorized_networks_dynamic(self):
        """Authorized networks use dynamic block."""
        resource = self.parsed["resources"]["google_sql_database_instance.this"]
        self.assertTrue(resource.get("dynamic"))

    def test_database_flags_dynamic(self):
        """Database flags use dynamic block."""
        resource = self.parsed["resources"]["google_sql_database_instance.this"]
        body = resource.get("body", "")
        self.assertIn("database_flags", body)

    def test_deletion_protection_variable(self):
        """Deletion protection variable exists."""
        self.assertIn("deletion_protection", self.parsed["variables"])

    def test_deletion_protection_default(self):
        """Deletion protection defaults to true."""
        dp = self.parsed["variables"].get("deletion_protection", {})
        self.assertEqual(dp.get("default"), "true")

    def test_backup_enabled_default(self):
        """Backup enabled defaults to true."""
        be = self.parsed["variables"].get("backup_enabled", {})
        self.assertEqual(be.get("default"), "true")

    def test_publicly_accessible_default(self):
        """Publicly accessible defaults to false."""
        pa = self.parsed["variables"].get("publicly_accessible", {})
        self.assertEqual(pa.get("default"), "false")

    def test_require_ssl_default(self):
        """Require SSL defaults to true."""
        ssl = self.parsed["variables"].get("require_ssl", {})
        self.assertEqual(ssl.get("default"), "true")

    def test_password_sensitive(self):
        """Password variable is sensitive."""
        pw = self.parsed["variables"].get("password", {})
        self.assertTrue(pw.get("sensitive"))

    def test_master_password_output_sensitive(self):
        """Master password output is sensitive."""
        pw = self.parsed["outputs"].get("master_password", {})
        self.assertTrue(pw.get("sensitive"))

    def test_prevent_destroy_lifecycle(self):
        """Prevent destroy lifecycle is configured."""
        resource = self.parsed["resources"]["google_sql_database_instance.this"]
        self.assertTrue(resource.get("lifecycle"))

    def test_availability_type_default(self):
        """Availability type defaults to REGIONAL."""
        at = self.parsed["variables"].get("availability_type", {})
        default_val = at.get("default", "").strip('"')
        self.assertEqual(default_val, "REGIONAL")

    def test_database_version_default(self):
        """Database version has default."""
        dv = self.parsed["variables"].get("database_version", {})
        self.assertIn("default", dv)

    def test_tier_default(self):
        """Tier has default."""
        tier = self.parsed["variables"].get("tier", {})
        self.assertIn("default", tier)

    def test_cloudsql_outputs(self):
        """Cloud SQL outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("instance_name", outputs)
        self.assertIn("instance_connection_name", outputs)
        self.assertIn("instance_self_link", outputs)
        self.assertIn("instance_ip_address", outputs)
        self.assertIn("instance_private_ip_address", outputs)
        self.assertIn("kms_key_id", outputs)
        self.assertIn("backup_enabled", outputs)
        self.assertIn("database_name", outputs)
        self.assertIn("master_password", outputs)


class TestGCPGCSModule(unittest.TestCase):
    """Tests for the GCP GCS module (storage - cross-cloud)."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "storage")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Storage module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_gcs_bucket_resource(self):
        """GCS bucket resource is defined."""
        self.assertIn("google_storage_bucket.this", self.parsed["resources"])

    def test_gcs_bucket_count(self):
        """GCS bucket uses count for conditional creation."""
        resource = self.parsed["resources"]["google_storage_bucket.this"]
        self.assertTrue(resource.get("count"))

    def test_gcs_uniform_bucket_level_access(self):
        """GCS bucket has uniform bucket level access."""
        resource = self.parsed["resources"]["google_storage_bucket.this"]
        body = resource.get("body", "")
        self.assertIn("uniform_bucket_level_access", body)
        self.assertIn("true", body)

    def test_gcs_versioning(self):
        """GCS bucket has versioning."""
        resource = self.parsed["resources"]["google_storage_bucket.this"]
        body = resource.get("body", "")
        self.assertIn("versioning", body)

    def test_gcs_encryption_dynamic(self):
        """GCS bucket has dynamic encryption block."""
        resource = self.parsed["resources"]["google_storage_bucket.this"]
        self.assertTrue(resource.get("dynamic"))

    def test_gcs_labels(self):
        """GCS bucket has labels."""
        resource = self.parsed["resources"]["google_storage_bucket.this"]
        body = resource.get("body", "")
        self.assertIn("labels", body)

    def test_enable_gcp_variable(self):
        """Enable GCP variable exists."""
        self.assertIn("enable_gcp", self.parsed["variables"])

    def test_gcp_location_variable(self):
        """GCP location variable exists."""
        self.assertIn("gcp_location", self.parsed["variables"])

    def test_storage_class_variable(self):
        """Storage class variable exists."""
        self.assertIn("storage_class", self.parsed["variables"])

    def test_enable_versioning_variable(self):
        """Enable versioning variable exists."""
        self.assertIn("enable_versioning", self.parsed["variables"])

    def test_enable_encryption_variable(self):
        """Enable encryption variable exists."""
        self.assertIn("enable_encryption", self.parsed["variables"])

    def test_gcp_kms_key_variable(self):
        """GCP KMS key variable exists."""
        self.assertIn("gcp_kms_key", self.parsed["variables"])

    def test_bucket_name_variable(self):
        """Bucket name variable exists."""
        self.assertIn("bucket_name", self.parsed["variables"])

    def test_environment_variable(self):
        """Environment variable exists."""
        self.assertIn("environment", self.parsed["variables"])


class TestGCPMonitoringModule(unittest.TestCase):
    """Tests for GCP Monitoring - verifies no dedicated module exists."""

    def test_no_dedicated_monitoring_module(self):
        """No dedicated GCP monitoring module exists in iac/modules."""
        monitoring_path = os.path.join(MODULES_BASE, "gcp", "monitoring")
        self.assertFalse(os.path.isdir(monitoring_path))

    def test_no_monitoring_in_terraform_modules(self):
        """No GCP monitoring module in terraform/modules."""
        monitoring_path = os.path.join(TERRAFORM_MODULES_BASE, "gcp", "monitoring")
        self.assertFalse(os.path.isdir(monitoring_path))


class TestGCPIAMModule(unittest.TestCase):
    """Tests for the GCP IAM module (identity - cross-cloud)."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "identity")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Identity module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_google_provider_declared(self):
        """Google provider is declared."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("google", providers)
        self.assertEqual(providers["google"]["source"], "hashicorp/google")

    def test_service_account_resource(self):
        """Service account resource is defined."""
        self.assertIn("google_service_account.workload", self.parsed["resources"])

    def test_service_account_count(self):
        """Service account uses count for conditional creation."""
        resource = self.parsed["resources"]["google_service_account.workload"]
        self.assertTrue(resource.get("count"))

    def test_project_iam_member_resource(self):
        """Project IAM member resource is defined."""
        self.assertIn("google_project_iam_member.workload", self.parsed["resources"])

    def test_project_iam_member_count(self):
        """Project IAM member uses count."""
        resource = self.parsed["resources"]["google_project_iam_member.workload"]
        self.assertTrue(resource.get("count"))

    def test_enable_gcp_variable(self):
        """Enable GCP variable exists."""
        self.assertIn("enable_gcp", self.parsed["variables"])

    def test_gcp_project_id_variable(self):
        """GCP project ID variable exists."""
        self.assertIn("gcp_project_id", self.parsed["variables"])

    def test_gcp_workload_roles_variable(self):
        """GCP workload roles variable exists."""
        self.assertIn("gcp_workload_roles", self.parsed["variables"])

    def test_project_name_variable(self):
        """Project name variable exists."""
        self.assertIn("project_name", self.parsed["variables"])

    def test_common_tags_variable(self):
        """Common tags variable exists."""
        self.assertIn("common_tags", self.parsed["variables"])


class TestGCPComplianceModules(unittest.TestCase):
    """Tests for GCP compliance modules in terraform/modules."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(TERRAFORM_MODULES_BASE)

    def test_organization_policies_module_exists(self):
        """Organization policies module exists in terraform/modules."""
        module_path = get_module_path(TERRAFORM_MODULES_BASE, "gcp-compliance", "organization-policies")
        self.assertTrue(os.path.isdir(module_path))

    def test_security_command_center_module_exists(self):
        """Security Command Center module exists in terraform/modules."""
        module_path = get_module_path(TERRAFORM_MODULES_BASE, "gcp-compliance", "security-command-center")
        self.assertTrue(os.path.isdir(module_path))

    def test_organization_policies_main_tf(self):
        """Organization policies main.tf exists."""
        main_tf = os.path.join(TERRAFORM_MODULES_BASE, "gcp-compliance", "organization-policies", "main.tf")
        self.assertTrue(os.path.exists(main_tf))

    def test_security_command_center_main_tf(self):
        """Security Command Center main.tf exists."""
        main_tf = os.path.join(TERRAFORM_MODULES_BASE, "gcp-compliance", "security-command-center", "main.tf")
        self.assertTrue(os.path.exists(main_tf))

    def test_organization_policies_main_tf_not_empty(self):
        """Organization policies main.tf is not empty."""
        main_tf = os.path.join(TERRAFORM_MODULES_BASE, "gcp-compliance", "organization-policies", "main.tf")
        content = read_tf_file(main_tf)
        self.assertGreater(len(content), 0)

    def test_security_command_center_variables_tf(self):
        """Security Command Center variables.tf exists."""
        variables_tf = os.path.join(TERRAFORM_MODULES_BASE, "gcp-compliance", "security-command-center", "variables.tf")
        self.assertTrue(os.path.exists(variables_tf))

    def test_security_command_center_outputs_tf(self):
        """Security Command Center outputs.tf exists."""
        outputs_tf = os.path.join(TERRAFORM_MODULES_BASE, "gcp-compliance", "security-command-center", "outputs.tf")
        self.assertTrue(os.path.exists(outputs_tf))


class TestGCPComplianceModulesIAC(unittest.TestCase):
    """Tests for GCP compliance modules in iac/modules."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)

    def test_cloud_audit_logs_module_exists(self):
        """Cloud Audit Logs module exists in iac/modules."""
        module_path = get_module_path(MODULES_BASE, "gcp-compliance", "cloud-audit-logs")
        self.assertTrue(os.path.isdir(module_path))

    def test_organization_policies_module_exists(self):
        """Organization Policies module exists in iac/modules."""
        module_path = get_module_path(MODULES_BASE, "gcp-compliance", "organization-policies")
        self.assertTrue(os.path.isdir(module_path))

    def test_security_command_center_module_exists(self):
        """Security Command Center module exists in iac/modules."""
        module_path = get_module_path(MODULES_BASE, "gcp-compliance", "security-command-center")
        self.assertTrue(os.path.isdir(module_path))

    def test_vpc_service_controls_module_exists(self):
        """VPC Service Controls module exists in iac/modules."""
        module_path = get_module_path(MODULES_BASE, "gcp-compliance", "vpc-service-controls")
        self.assertTrue(os.path.isdir(module_path))

    def test_cloud_audit_logs_resources(self):
        """Cloud Audit Logs has required resources."""
        module_path = get_module_path(MODULES_BASE, "gcp-compliance", "cloud-audit-logs")
        parsed = self.parser.parse_module(module_path)
        self.assertIn("google_project_iam_audit_config.project", parsed["resources"])
        self.assertIn("google_folder_iam_audit_config.folder", parsed["resources"])
        self.assertIn("google_organization_iam_audit_config.organization", parsed["resources"])

    def test_organization_policies_resources(self):
        """Organization Policies has required resources."""
        module_path = get_module_path(MODULES_BASE, "gcp-compliance", "organization-policies")
        parsed = self.parser.parse_module(module_path)
        self.assertIn("google_org_policy_policy.disable_serial_port", parsed["resources"])
        self.assertIn("google_org_policy_policy.require_os_login", parsed["resources"])
        self.assertIn("google_org_policy_policy.restrict_vm_external_ips", parsed["resources"])

    def test_security_command_center_resources(self):
        """Security Command Center has required resources."""
        module_path = get_module_path(MODULES_BASE, "gcp-compliance", "security-command-center")
        parsed = self.parser.parse_module(module_path)
        self.assertIn("google_scc_source.this", parsed["resources"])
        self.assertIn("google_scc_notification_config.this", parsed["resources"])

    def test_vpc_service_controls_resources(self):
        """VPC Service Controls has required resources."""
        module_path = get_module_path(MODULES_BASE, "gcp-compliance", "vpc-service-controls")
        parsed = self.parser.parse_module(module_path)
        self.assertIn("google_access_context_manager_access_policy.this", parsed["resources"])
        self.assertIn("google_access_context_manager_service_perimeter.this", parsed["resources"])


class TestGCPModuleProviderConsistency(unittest.TestCase):
    """Tests for provider consistency across GCP modules."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)

    def test_network_gcp_google_provider(self):
        """Network GCP module uses google provider."""
        module_path = get_module_path(MODULES_BASE, "network", "gcp")
        parsed = self.parser.parse_module(module_path)
        providers = parsed["terraform_config"].get("required_providers", {})
        self.assertIn("google", providers)
        self.assertEqual(providers["google"]["source"], "hashicorp/google")

    def test_compute_gcp_google_provider(self):
        """Compute GCP module uses google provider."""
        module_path = get_module_path(MODULES_BASE, "compute", "gcp")
        parsed = self.parser.parse_module(module_path)
        providers = parsed["terraform_config"].get("required_providers", {})
        self.assertIn("google", providers)
        self.assertEqual(providers["google"]["source"], "hashicorp/google")

    def test_identity_google_provider(self):
        """Identity module uses google provider."""
        module_path = get_module_path(MODULES_BASE, "identity")
        parsed = self.parser.parse_module(module_path)
        providers = parsed["terraform_config"].get("required_providers", {})
        self.assertIn("google", providers)
        self.assertEqual(providers["google"]["source"], "hashicorp/google")

    def test_storage_google_provider(self):
        """Storage module uses google provider."""
        module_path = get_module_path(MODULES_BASE, "storage")
        parsed = self.parser.parse_module(module_path)
        providers = parsed["terraform_config"].get("required_providers", {})
        self.assertIn("google", providers)
        self.assertEqual(providers["google"]["source"], "hashicorp/google")


class TestGCPModuleVersionConsistency(unittest.TestCase):
    """Tests for version consistency across GCP modules."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)

    def test_network_gcp_version(self):
        """Network GCP module has version constraint."""
        module_path = get_module_path(MODULES_BASE, "network", "gcp")
        parsed = self.parser.parse_module(module_path)
        self.assertIn("required_version", parsed["terraform_config"])

    def test_compute_gcp_version(self):
        """Compute GCP module has version constraint."""
        module_path = get_module_path(MODULES_BASE, "compute", "gcp")
        parsed = self.parser.parse_module(module_path)
        self.assertIn("required_version", parsed["terraform_config"])

    def test_identity_version(self):
        """Identity module has version constraint."""
        module_path = get_module_path(MODULES_BASE, "identity")
        parsed = self.parser.parse_module(module_path)
        self.assertIn("required_version", parsed["terraform_config"])

    def test_storage_version(self):
        """Storage module has version constraint."""
        module_path = get_module_path(MODULES_BASE, "storage")
        parsed = self.parser.parse_module(module_path)
        self.assertIn("required_version", parsed["terraform_config"])


if __name__ == "__main__":
    unittest.main()
