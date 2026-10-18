"""
Other Providers Module Tests
============================
Tests for Huawei, Alibaba, Oracle, IBM, DigitalOcean, and CloudStack modules.
"""

import os
import re
import unittest
from pathlib import Path

from tests.terraform.terraform_parser import TerraformParser, get_module_path


MODULES_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "iac", "modules"))


# ============================================================
# HUAWEI MODULE TESTS
# ============================================================

class TestHuaweiVPCModule(unittest.TestCase):
    """Tests for the Huawei VPC module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "huawei", "vpc")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Huawei VPC module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_vpc_resource(self):
        """Huawei VPC resource exists."""
        self.assertIn("huaweicloud_vpc_v1.this", self.parsed["resources"])

    def test_subnet_resource(self):
        """Subnet resource exists."""
        self.assertIn("huaweicloud_vpc_subnet_v1.this", self.parsed["resources"])

    def test_security_group_resource(self):
        """Security group resource exists."""
        self.assertIn("huaweicloud_networking_secgroup_v2.this", self.parsed["resources"])

    def test_security_group_rule_resource(self):
        """Security group rule resource exists."""
        self.assertIn("huaweicloud_networking_secgroup_rule_v2.this", self.parsed["resources"])

    def test_cidr_validation(self):
        """CIDR has validation."""
        cidr = self.parsed["variables"].get("cidr", {})
        self.assertIn("validation", cidr)
        self.assertIn("cidrhost", cidr["validation"]["condition"])

    def test_huawei_provider(self):
        """Huawei provider is declared."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("huaweicloud", providers)
        self.assertEqual(providers["huaweicloud"]["source"], "huaweicloud/huaweicloud")

    def test_vpc_outputs(self):
        """VPC outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("vpc_id", outputs)
        self.assertIn("vpc_name", outputs)
        self.assertIn("subnet_ids", outputs)
        self.assertIn("security_group_id", outputs)


class TestHuaweiECSModule(unittest.TestCase):
    """Tests for the Huawei ECS module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "huawei", "ecs")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Huawei ECS module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_instance_resource(self):
        """ECS instance resource exists."""
        self.assertIn("huaweicloud_compute_instance_v2.this", self.parsed["resources"])

    def test_eip_associate_resource(self):
        """EIP associate resource exists."""
        self.assertIn("huaweicloud_compute_eip_associate.this", self.parsed["resources"])

    def test_image_data_source(self):
        """Image data source exists."""
        self.assertIn("huaweicloud_images_image_v2.this", self.parsed["data_sources"])

    def test_availability_zones_data_source(self):
        """Availability zones data source exists."""
        self.assertIn("huaweicloud_availability_zones.this", self.parsed["data_sources"])

    def test_count_validation(self):
        """Count has validation."""
        count = self.parsed["variables"].get("count", {})
        self.assertIn("validation", count)
        self.assertIn("count > 0", count["validation"]["condition"])

    def test_ecs_outputs(self):
        """ECS outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("instance_ids", outputs)
        self.assertIn("instance_names", outputs)
        self.assertIn("instance_ips", outputs)
        self.assertIn("eip_address", outputs)


class TestHuaweiEVSModule(unittest.TestCase):
    """Tests for the Huawei EVS module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "huawei", "evs")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Huawei EVS module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_volume_resource(self):
        """EVS volume resource exists."""
        self.assertIn("huaweicloud_evs_volume_v3.this", self.parsed["resources"])

    def test_volume_attach_resource(self):
        """Volume attach resource exists."""
        self.assertIn("huaweicloud_compute_volume_attach_v2.this", self.parsed["resources"])

    def test_volume_type_validation(self):
        """Volume type has validation."""
        vt = self.parsed["variables"].get("volume_type", {})
        self.assertIn("validation", vt)
        self.assertIn("SAS", vt["validation"]["condition"])
        self.assertIn("SSD", vt["validation"]["condition"])
        self.assertIn("GPSSD", vt["validation"]["condition"])
        self.assertIn("ESSD", vt["validation"]["condition"])

    def test_size_validation(self):
        """Size has validation."""
        size = self.parsed["variables"].get("size", {})
        self.assertIn("validation", size)
        self.assertIn("size >= 10", size["validation"]["condition"])

    def test_multiattach_support(self):
        """Multiattach is supported."""
        self.assertIn("multiattach", self.parsed["variables"])

    def test_evs_outputs(self):
        """EVS outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("volume_ids", outputs)
        self.assertIn("volume_names", outputs)
        self.assertIn("attachment_ids", outputs)


class TestHuaweiELBModule(unittest.TestCase):
    """Tests for the Huawei ELB module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "huawei", "elb")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Huawei ELB module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_loadbalancer_resource(self):
        """Load balancer resource exists."""
        self.assertIn("huaweicloud_lb_loadbalancer_v3.this", self.parsed["resources"])

    def test_listener_resource(self):
        """Listener resource exists."""
        self.assertIn("huaweicloud_lb_listener_v3.this", self.parsed["resources"])

    def test_pool_resource(self):
        """Pool resource exists."""
        self.assertIn("huaweicloud_lb_pool_v3.this", self.parsed["resources"])

    def test_member_resource(self):
        """Member resource exists."""
        self.assertIn("huaweicloud_lb_member_v3.this", self.parsed["resources"])

    def test_monitor_resource(self):
        """Monitor resource exists."""
        self.assertIn("huaweicloud_lb_monitor_v3.this", self.parsed["resources"])

    def test_dynamic_listener_rules(self):
        """Dynamic listener rules are used."""
        resource = self.parsed["resources"]["huaweicloud_lb_listener_v3.this"]
        self.assertTrue(resource.get("dynamic"))

    def test_elb_outputs(self):
        """ELB outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("loadbalancer_id", outputs)
        self.assertIn("loadbalancer_name", outputs)
        self.assertIn("loadbalancer_vip", outputs)
        self.assertIn("listener_ids", outputs)
        self.assertIn("pool_ids", outputs)


# ============================================================
# ALIBABA MODULE TESTS
# ============================================================

class TestAlibabaVPCModule(unittest.TestCase):
    """Tests for the Alibaba VPC module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "alibaba", "vpc")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Alibaba VPC module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_vpc_resource(self):
        """Alibaba VPC resource exists."""
        self.assertIn("alicloud_vpc.this", self.parsed["resources"])

    def test_vswitch_resource(self):
        """VSwitch resource exists."""
        self.assertIn("alicloud_vswitch.this", self.parsed["resources"])

    def test_security_group_resource(self):
        """Security group resource exists."""
        self.assertIn("alicloud_security_group.this", self.parsed["resources"])

    def test_security_group_rule_resource(self):
        """Security group rule resource exists."""
        self.assertIn("alicloud_security_group_rule.this", self.parsed["resources"])

    def test_cidr_validation(self):
        """CIDR has validation."""
        cidr = self.parsed["variables"].get("cidr_block", {})
        self.assertIn("validation", cidr)
        self.assertIn("cidrhost", cidr["validation"]["condition"])

    def test_alibaba_provider(self):
        """Alibaba provider is declared."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("alicloud", providers)
        self.assertEqual(providers["alicloud"]["source"], "aliyun/alicloud")

    def test_vpc_outputs(self):
        """VPC outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("vpc_id", outputs)
        self.assertIn("vpc_name", outputs)
        self.assertIn("vswitch_ids", outputs)
        self.assertIn("security_group_id", outputs)


class TestAlibabaECSModule(unittest.TestCase):
    """Tests for the Alibaba ECS module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "alibaba", "ecs")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Alibaba ECS module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_instance_resource(self):
        """ECS instance resource exists."""
        self.assertIn("alicloud_instance.this", self.parsed["resources"])

    def test_eip_resource(self):
        """EIP resource exists."""
        self.assertIn("alicloud_eip_address.this", self.parsed["resources"])

    def test_eip_association_resource(self):
        """EIP association resource exists."""
        self.assertIn("alicloud_eip_association.this", self.parsed["resources"])

    def test_zones_data_source(self):
        """Zones data source exists."""
        self.assertIn("alicloud_zones.this", self.parsed["data_sources"])

    def test_images_data_source(self):
        """Images data source exists."""
        self.assertIn("alicloud_images.this", self.parsed["data_sources"])

    def test_count_validation(self):
        """Count has validation."""
        count = self.parsed["variables"].get("count", {})
        self.assertIn("validation", count)
        self.assertIn("count > 0", count["validation"]["condition"])

    def test_disk_category_validation(self):
        """Disk category has validation."""
        dc = self.parsed["variables"].get("system_disk_category", {})
        self.assertIn("validation", dc)
        self.assertIn("cloud_essd", dc["validation"]["condition"])

    def test_ecs_outputs(self):
        """ECS outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("instance_ids", outputs)
        self.assertIn("instance_names", outputs)
        self.assertIn("instance_ips", outputs)
        self.assertIn("eip_address", outputs)


class TestAlibabaDiskModule(unittest.TestCase):
    """Tests for the Alibaba Disk module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "alibaba", "disk")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Alibaba Disk module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_disk_resource(self):
        """Disk resource exists."""
        self.assertIn("alicloud_disk.this", self.parsed["resources"])

    def test_disk_attachment_resource(self):
        """Disk attachment resource exists."""
        self.assertIn("alicloud_disk_attachment.this", self.parsed["resources"])

    def test_size_validation(self):
        """Size has validation."""
        size = self.parsed["variables"].get("size", {})
        self.assertIn("validation", size)
        self.assertIn("size >= 20", size["validation"]["condition"])

    def test_category_validation(self):
        """Category has validation."""
        cat = self.parsed["variables"].get("category", {})
        self.assertIn("validation", cat)
        self.assertIn("cloud_essd", cat["validation"]["condition"])

    def test_encryption_support(self):
        """Encryption is supported."""
        self.assertIn("encrypted", self.parsed["variables"])
        self.assertIn("kms_key_id", self.parsed["variables"])

    def test_disk_outputs(self):
        """Disk outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("disk_ids", outputs)
        self.assertIn("disk_names", outputs)
        self.assertIn("attachment_ids", outputs)


class TestAlibabaSLBModule(unittest.TestCase):
    """Tests for the Alibaba SLB module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "alibaba", "slb")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Alibaba SLB module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_loadbalancer_resource(self):
        """SLB load balancer resource exists."""
        self.assertIn("alicloud_slb_load_balancer.this", self.parsed["resources"])

    def test_listener_resource(self):
        """Listener resource exists."""
        self.assertIn("alicloud_slb_listener.this", self.parsed["resources"])

    def test_backend_server_resource(self):
        """Backend server resource exists."""
        self.assertIn("alicloud_slb_backend_server.this", self.parsed["resources"])

    def test_address_type_validation(self):
        """Address type has validation."""
        at = self.parsed["variables"].get("address_type", {})
        self.assertIn("validation", at)
        self.assertIn("internet", at["validation"]["condition"])
        self.assertIn("intranet", at["validation"]["condition"])

    def test_slb_outputs(self):
        """SLB outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("loadbalancer_id", outputs)
        self.assertIn("loadbalancer_name", outputs)
        self.assertIn("loadbalancer_address", outputs)
        self.assertIn("listener_ids", outputs)


# ============================================================
# ORACLE MODULE TESTS
# ============================================================

class TestOracleVCNModule(unittest.TestCase):
    """Tests for the Oracle VCN module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "oracle", "vcn")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Oracle VCN module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_vcn_resource(self):
        """VCN resource exists."""
        self.assertIn("oci_core_vcn.this", self.parsed["resources"])

    def test_subnet_resource(self):
        """Subnet resource exists."""
        self.assertIn("oci_core_subnet.this", self.parsed["resources"])

    def test_internet_gateway_resource(self):
        """Internet gateway resource exists."""
        self.assertIn("oci_core_internet_gateway.this", self.parsed["resources"])

    def test_route_table_resource(self):
        """Route table resource exists."""
        self.assertIn("oci_core_route_table.this", self.parsed["resources"])

    def test_security_list_resource(self):
        """Security list resource exists."""
        self.assertIn("oci_core_security_list.this", self.parsed["resources"])

    def test_cidr_blocks_validation(self):
        """CIDR blocks has validation."""
        cidr = self.parsed["variables"].get("cidr_blocks", {})
        self.assertIn("validation", cidr)
        self.assertIn("length(var.cidr_blocks) > 0", cidr["validation"]["condition"])

    def test_oracle_provider(self):
        """Oracle provider is declared."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("oci", providers)
        self.assertEqual(providers["oci"]["source"], "oracle/oci")

    def test_dynamic_route_rules(self):
        """Dynamic route rules are used."""
        resource = self.parsed["resources"]["oci_core_route_table.this"]
        self.assertTrue(resource.get("dynamic"))

    def test_dynamic_ingress_rules(self):
        """Dynamic ingress rules are used."""
        resource = self.parsed["resources"]["oci_core_security_list.this"]
        self.assertTrue(resource.get("dynamic"))

    def test_vcn_outputs(self):
        """VCN outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("vcn_id", outputs)
        self.assertIn("vcn_name", outputs)
        self.assertIn("subnet_ids", outputs)
        self.assertIn("internet_gateway_id", outputs)
        self.assertIn("route_table_id", outputs)
        self.assertIn("security_list_id", outputs)


class TestOracleComputeModule(unittest.TestCase):
    """Tests for the Oracle Compute module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "oracle", "compute")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Oracle Compute module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_instance_resource(self):
        """Compute instance resource exists."""
        self.assertIn("oci_core_instance.this", self.parsed["resources"])

    def test_vnic_attachment_resource(self):
        """VNIC attachment resource exists."""
        self.assertIn("oci_core_vnic_attachment.this", self.parsed["resources"])

    def test_availability_domains_data_source(self):
        """Availability domains data source exists."""
        self.assertIn("oci_identity_availability_domains.this", self.parsed["data_sources"])

    def test_images_data_source(self):
        """Images data source exists."""
        self.assertIn("oci_core_images.this", self.parsed["data_sources"])

    def test_count_validation(self):
        """Count has validation."""
        count = self.parsed["variables"].get("count", {})
        self.assertIn("validation", count)
        self.assertIn("count > 0", count["validation"]["condition"])

    def test_compute_outputs(self):
        """Compute outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("instance_ids", outputs)
        self.assertIn("instance_names", outputs)
        self.assertIn("instance_public_ips", outputs)
        self.assertIn("instance_private_ips", outputs)


class TestOracleVolumeModule(unittest.TestCase):
    """Tests for the Oracle Volume module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "oracle", "volume")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Oracle Volume module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_volume_resource(self):
        """Volume resource exists."""
        self.assertIn("oci_core_volume.this", self.parsed["resources"])

    def test_volume_attachment_resource(self):
        """Volume attachment resource exists."""
        self.assertIn("oci_core_volume_attachment.this", self.parsed["resources"])

    def test_backup_policy_resource(self):
        """Backup policy resource exists."""
        self.assertIn("oci_core_volume_backup_policy.this", self.parsed["resources"])

    def test_size_validation(self):
        """Size has validation."""
        size = self.parsed["variables"].get("size_in_gbs", {})
        self.assertIn("validation", size)
        self.assertIn("size_in_gbs >= 50", size["validation"]["condition"])

    def test_vpus_per_gb_validation(self):
        """VPUs per GB has validation."""
        vpus = self.parsed["variables"].get("vpus_per_gb", {})
        self.assertIn("validation", vpus)
        self.assertIn("10", vpus["validation"]["condition"])

    def test_attachment_type_validation(self):
        """Attachment type has validation."""
        at = self.parsed["variables"].get("attachment_type", {})
        self.assertIn("validation", at)
        self.assertIn("paravirtualized", at["validation"]["condition"])
        self.assertIn("iscsi", at["validation"]["condition"])

    def test_volume_outputs(self):
        """Volume outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("volume_ids", outputs)
        self.assertIn("volume_names", outputs)
        self.assertIn("attachment_ids", outputs)
        self.assertIn("backup_policy_id", outputs)


class TestOracleLoadBalancerModule(unittest.TestCase):
    """Tests for the Oracle Load Balancer module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "oracle", "load-balancer")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Oracle Load Balancer module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_loadbalancer_resource(self):
        """Load balancer resource exists."""
        self.assertIn("oci_load_balancer_load_balancer.this", self.parsed["resources"])

    def test_backend_set_resource(self):
        """Backend set resource exists."""
        self.assertIn("oci_load_balancer_backend_set.this", self.parsed["resources"])

    def test_backend_resource(self):
        """Backend resource exists."""
        self.assertIn("oci_load_balancer_backend.this", self.parsed["resources"])

    def test_listener_resource(self):
        """Listener resource exists."""
        self.assertIn("oci_load_balancer_listener.this", self.parsed["resources"])

    def test_certificate_resource(self):
        """Certificate resource exists."""
        self.assertIn("oci_load_balancer_certificate.this", self.parsed["resources"])

    def test_shape_validation(self):
        """Shape has validation."""
        shape = self.parsed["variables"].get("shape", {})
        self.assertIn("validation", shape)
        self.assertIn("flexible", shape["validation"]["condition"])

    def test_lb_outputs(self):
        """Load balancer outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("loadbalancer_id", outputs)
        self.assertIn("loadbalancer_name", outputs)
        self.assertIn("loadbalancer_ip", outputs)
        self.assertIn("backend_set_ids", outputs)
        self.assertIn("listener_ids", outputs)


# ============================================================
# IBM MODULE TESTS
# ============================================================

class TestIBMVPCModule(unittest.TestCase):
    """Tests for the IBM VPC module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "ibm", "vpc")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """IBM VPC module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_vpc_resource(self):
        """IBM VPC resource exists."""
        self.assertIn("ibm_is_vpc.this", self.parsed["resources"])

    def test_address_prefix_resource(self):
        """Address prefix resource exists."""
        self.assertIn("ibm_is_vpc_address_prefix.this", self.parsed["resources"])

    def test_subnet_resource(self):
        """Subnet resource exists."""
        self.assertIn("ibm_is_subnet.this", self.parsed["resources"])

    def test_network_acl_resource(self):
        """Network ACL resource exists."""
        self.assertIn("ibm_is_network_acl.this", self.parsed["resources"])

    def test_public_gateway_resource(self):
        """Public gateway resource exists."""
        self.assertIn("ibm_is_public_gateway.this", self.parsed["resources"])

    def test_security_group_resource(self):
        """Security group resource exists."""
        self.assertIn("ibm_is_security_group.this", self.parsed["resources"])

    def test_security_group_rule_resource(self):
        """Security group rule resource exists."""
        self.assertIn("ibm_is_security_group_rule.this", self.parsed["resources"])

    def test_flow_log_resource(self):
        """Flow log resource exists."""
        self.assertIn("ibm_is_flow_log.this", self.parsed["resources"])

    def test_address_prefix_management_validation(self):
        """Address prefix management has validation."""
        apm = self.parsed["variables"].get("address_prefix_management", {})
        self.assertIn("validation", apm)
        self.assertIn("auto", apm["validation"]["condition"])
        self.assertIn("manual", apm["validation"]["condition"])

    def test_classic_access_default(self):
        """Classic access defaults to false."""
        ca = self.parsed["variables"].get("classic_access", {})
        self.assertEqual(ca.get("default"), "false")

    def test_vpc_outputs(self):
        """VPC outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("vpc_id", outputs)
        self.assertIn("vpc_crn", outputs)
        self.assertIn("vpc_name", outputs)
        self.assertIn("subnet_ids", outputs)
        self.assertIn("subnet_crns", outputs)
        self.assertIn("public_gateway_ids", outputs)
        self.assertIn("security_group_id", outputs)
        self.assertIn("network_acl_id", outputs)
        self.assertIn("flow_log_id", outputs)

    def test_ibm_provider(self):
        """IBM provider is declared."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("ibm", providers)
        self.assertEqual(providers["ibm"]["source"], "IBM-Cloud/ibm")

    def test_dynamic_network_acl_rules(self):
        """Dynamic network ACL rules are used."""
        resource = self.parsed["resources"]["ibm_is_network_acl.this"]
        self.assertTrue(resource.get("dynamic"))

    def test_dynamic_security_group_rules(self):
        """Dynamic security group rules are used."""
        resource = self.parsed["resources"]["ibm_is_security_group_rule.this"]
        self.assertTrue(resource.get("dynamic"))


class TestIBMVSIModule(unittest.TestCase):
    """Tests for the IBM VSI module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "ibm", "vsi")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """IBM VSI module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_instance_resource(self):
        """IBM instance resource exists."""
        self.assertIn("ibm_is_instance.this", self.parsed["resources"])

    def test_floating_ip_resource(self):
        """Floating IP resource exists."""
        self.assertIn("ibm_is_floating_ip.this", self.parsed["resources"])

    def test_image_data_source(self):
        """Image data source exists."""
        self.assertIn("ibm_is_image.this", self.parsed["data_sources"])

    def test_ssh_key_data_source(self):
        """SSH key data source exists."""
        self.assertIn("ibm_is_ssh_key.this", self.parsed["data_sources"])

    def test_vsi_outputs(self):
        """VSI outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("instance_id", outputs)
        self.assertIn("instance_crn", outputs)
        self.assertIn("instance_name", outputs)
        self.assertIn("primary_ip", outputs)
        self.assertIn("floating_ip", outputs)
        self.assertIn("floating_ip_id", outputs)

    def test_enable_floating_ip_default(self):
        """Floating IP defaults to disabled."""
        fip = self.parsed["variables"].get("enable_floating_ip", {})
        self.assertEqual(fip.get("default"), "false")

    def test_boot_volume_size_default(self):
        """Boot volume size defaults to 100 GB."""
        bvs = self.parsed["variables"].get("boot_volume_size", {})
        self.assertEqual(bvs.get("default"), "100")


class TestIBMBlockStorageModule(unittest.TestCase):
    """Tests for the IBM Block Storage module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "ibm", "block-storage")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """IBM Block Storage module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_volume_resource(self):
        """IBM volume resource exists."""
        self.assertIn("ibm_is_volume.this", self.parsed["resources"])

    def test_volume_attachment_resource(self):
        """Volume attachment resource exists."""
        self.assertIn("ibm_is_instance_volume_attachment.this", self.parsed["resources"])

    def test_profile_validation(self):
        """Profile has validation."""
        prof = self.parsed["variables"].get("profile", {})
        self.assertIn("validation", prof)
        self.assertIn("10iops-tier", prof["validation"]["condition"])
        self.assertIn("5iops-tier", prof["validation"]["condition"])
        self.assertIn("general-purpose", prof["validation"]["condition"])
        self.assertIn("custom", prof["validation"]["condition"])

    def test_encryption_key_support(self):
        """Encryption key is supported."""
        self.assertIn("encryption_key_crn", self.parsed["variables"])

    def test_volume_outputs(self):
        """Volume outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("volume_id", outputs)
        self.assertIn("volume_crn", outputs)
        self.assertIn("volume_name", outputs)
        self.assertIn("volume_capacity", outputs)
        self.assertIn("attachment_id", outputs)


class TestIBMIAMModule(unittest.TestCase):
    """Tests for the IBM IAM module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "ibm", "iam")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """IBM IAM module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_access_group_resource(self):
        """Access group resource exists."""
        self.assertIn("ibm_iam_access_group.this", self.parsed["resources"])

    def test_access_group_members_resource(self):
        """Access group members resource exists."""
        self.assertIn("ibm_iam_access_group_members.this", self.parsed["resources"])

    def test_access_group_policy_resource(self):
        """Access group policy resource exists."""
        self.assertIn("ibm_iam_access_group_policy.this", self.parsed["resources"])

    def test_dynamic_rule_resource(self):
        """Dynamic rule resource exists."""
        self.assertIn("ibm_iam_access_group_dynamic_rule.this", self.parsed["resources"])

    def test_iam_outputs(self):
        """IAM outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("access_group_id", outputs)
        self.assertIn("access_group_name", outputs)
        self.assertIn("access_group_crn", outputs)
        self.assertIn("policy_ids", outputs)
        self.assertIn("dynamic_rule_ids", outputs)


class TestIBMObjectStorageModule(unittest.TestCase):
    """Tests for the IBM Object Storage module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "ibm", "object-storage")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """IBM Object Storage module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_cos_bucket_resource(self):
        """COS bucket resource exists."""
        self.assertIn("ibm_cos_bucket.this", self.parsed["resources"])

    def test_versioning_resource(self):
        """Versioning resource exists."""
        self.assertIn("ibm_cos_bucket_versioning.this", self.parsed["resources"])

    def test_lifecycle_configuration_resource(self):
        """Lifecycle configuration resource exists."""
        self.assertIn("ibm_cos_bucket_lifecycle_configuration.this", self.parsed["resources"])

    def test_storage_class_validation(self):
        """Storage class has validation."""
        sc = self.parsed["variables"].get("storage_class", {})
        self.assertIn("validation", sc)
        self.assertIn("standard", sc["validation"]["condition"])
        self.assertIn("vault", sc["validation"]["condition"])
        self.assertIn("cold", sc["validation"]["condition"])
        self.assertIn("smart", sc["validation"]["condition"])

    def test_encryption_key_support(self):
        """Encryption key is supported."""
        self.assertIn("encryption_key_crn", self.parsed["variables"])

    def test_activity_tracking_support(self):
        """Activity tracking is supported."""
        self.assertIn("enable_activity_tracking", self.parsed["variables"])

    def test_metrics_monitoring_support(self):
        """Metrics monitoring is supported."""
        self.assertIn("enable_metrics_monitoring", self.parsed["variables"])

    def test_allowed_ips_support(self):
        """Allowed IPs are supported."""
        self.assertIn("allowed_ips", self.parsed["variables"])

    def test_lifecycle_rules_support(self):
        """Lifecycle rules are supported."""
        self.assertIn("lifecycle_rules", self.parsed["variables"])

    def test_object_storage_outputs(self):
        """Object storage outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("bucket_id", outputs)
        self.assertIn("bucket_crn", outputs)
        self.assertIn("bucket_name", outputs)
        self.assertIn("bucket_location", outputs)
        self.assertIn("s3_endpoint", outputs)

    def test_dynamic_blocks(self):
        """Dynamic blocks are used for optional features."""
        resource = self.parsed["resources"]["ibm_cos_bucket.this"]
        self.assertTrue(resource.get("dynamic"))


# ============================================================
# DIGITALOCEAN MODULE TESTS
# ============================================================

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


# ============================================================
# CLOUDSTACK MODULE TESTS
# ============================================================

class TestCloudStackInstanceModule(unittest.TestCase):
    """Tests for the CloudStack Instance module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "cloudstack", "instance")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """CloudStack Instance module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_instance_resource(self):
        """Instance resource exists."""
        self.assertIn("cloudstack_instance.this", self.parsed["resources"])

    def test_static_nat_resource(self):
        """Static NAT resource exists."""
        self.assertIn("cloudstack_static_nat.this", self.parsed["resources"])

    def test_port_forward_resource(self):
        """Port forward resource exists."""
        self.assertIn("cloudstack_port_forward.this", self.parsed["resources"])

    def test_template_data_source(self):
        """Template data source exists."""
        self.assertIn("cloudstack_template.this", self.parsed["data_sources"])

    def test_count_validation(self):
        """Count has validation."""
        count = self.parsed["variables"].get("count", {})
        self.assertIn("validation", count)
        self.assertIn("count > 0", count["validation"]["condition"])

    def test_dynamic_nic(self):
        """Dynamic NIC block is used."""
        resource = self.parsed["resources"]["cloudstack_instance.this"]
        self.assertTrue(resource.get("dynamic"))

    def test_cloudstack_provider(self):
        """CloudStack provider is declared."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("cloudstack", providers)
        self.assertEqual(providers["cloudstack"]["source"], "cloudstack/cloudstack")

    def test_instance_outputs(self):
        """Instance outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("instance_ids", outputs)
        self.assertIn("instance_names", outputs)
        self.assertIn("instance_ips", outputs)


class TestCloudStackVolumeModule(unittest.TestCase):
    """Tests for the CloudStack Volume module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "cloudstack", "volume")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """CloudStack Volume module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_disk_resource(self):
        """Disk resource exists."""
        self.assertIn("cloudstack_disk.this", self.parsed["resources"])

    def test_volume_resource(self):
        """Volume resource exists."""
        self.assertIn("cloudstack_volume.this", self.parsed["resources"])

    def test_count_validation(self):
        """Count has validation."""
        count = self.parsed["variables"].get("count", {})
        self.assertIn("validation", count)
        self.assertIn("count > 0", count["validation"]["condition"])

    def test_volume_outputs(self):
        """Volume outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("disk_ids", outputs)
        self.assertIn("disk_names", outputs)
        self.assertIn("volume_id", outputs)


class TestCloudStackNetworkModule(unittest.TestCase):
    """Tests for the CloudStack Network module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "cloudstack", "network")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """CloudStack Network module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_network_resource(self):
        """Network resource exists."""
        self.assertIn("cloudstack_network.this", self.parsed["resources"])

    def test_ipaddress_resource(self):
        """IP address resource exists."""
        self.assertIn("cloudstack_ipaddress.this", self.parsed["resources"])

    def test_firewall_resource(self):
        """Firewall resource exists."""
        self.assertIn("cloudstack_firewall.this", self.parsed["resources"])

    def test_egress_firewall_resource(self):
        """Egress firewall resource exists."""
        self.assertIn("cloudstack_egress_firewall.this", self.parsed["resources"])

    def test_network_outputs(self):
        """Network outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("network_id", outputs)
        self.assertIn("network_name", outputs)
        self.assertIn("ip_address_id", outputs)


class TestCloudStackSecurityGroupModule(unittest.TestCase):
    """Tests for the CloudStack Security Group module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "cloudstack", "security-group")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """CloudStack Security Group module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_security_group_resource(self):
        """Security group resource exists."""
        self.assertIn("cloudstack_security_group.this", self.parsed["resources"])

    def test_security_group_rule_resource(self):
        """Security group rule resource exists."""
        self.assertIn("cloudstack_security_group_rule.this", self.parsed["resources"])

    def test_security_group_outputs(self):
        """Security group outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("security_group_id", outputs)
        self.assertIn("security_group_name", outputs)


if __name__ == "__main__":
    unittest.main()
