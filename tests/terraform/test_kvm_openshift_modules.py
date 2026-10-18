"""
KVM and OpenShift Module Tests
===============================
Tests for KVM virtualization and OpenShift modules.
"""

import os
import re
import unittest
from pathlib import Path

from tests.terraform.terraform_parser import TerraformParser, get_module_path


MODULES_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "terraform", "modules"))


class TestKVMModule(unittest.TestCase):
    """Tests for the KVM module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "kvm")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """KVM module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_storage_pool_resource(self):
        """Storage pool resource exists."""
        self.assertIn("libvirt_pool.kvm_storage_pool", self.parsed["resources"])

    def test_base_volume_resource(self):
        """Base volume resource exists."""
        self.assertIn("libvirt_volume.base_volume", self.parsed["resources"])

    def test_vm_root_disk_resource(self):
        """VM root disk resource exists."""
        self.assertIn("libvirt_volume.vm_root_disk", self.parsed["resources"])

    def test_cloudinit_resource(self):
        """Cloud-init resource exists."""
        self.assertIn("libvirt_cloudinit_disk.vm_cloud_init", self.parsed["resources"])

    def test_vm_domain_resource(self):
        """VM domain resource exists."""
        self.assertIn("libvirt_domain.vm", self.parsed["resources"])

    def test_extra_disk_resource(self):
        """Extra disk resource exists."""
        self.assertIn("libvirt_volume.vm_extra_disk", self.parsed["resources"])

    def test_network_resource(self):
        """Network resource exists."""
        self.assertIn("libvirt_network.kvm_networks", self.parsed["resources"])

    def test_kvm_outputs(self):
        """KVM outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("vm_id", outputs)
        self.assertIn("vm_name", outputs)
        self.assertIn("vm_memory", outputs)
        self.assertIn("vm_vcpu", outputs)
        self.assertIn("vm_network_interfaces", outputs)
        self.assertIn("vm_ip_addresses", outputs)

    def test_libvirt_provider_config(self):
        """Libvirt provider is configured."""
        self.assertIn("libvirt", self.parsed["providers"])

    def test_dynamic_network_interface(self):
        """Dynamic network interface is used."""
        resource = self.parsed["resources"]["libvirt_domain.vm"]
        self.assertTrue(resource.get("dynamic"))

    def test_dynamic_extra_volumes(self):
        """Dynamic extra volumes are used."""
        resource = self.parsed["resources"]["libvirt_domain.vm"]
        self.assertTrue(resource.get("dynamic"))

    def test_vm_autostart_default(self):
        """VM autostart defaults to true."""
        auto = self.parsed["variables"].get("vm_autostart", {})
        self.assertEqual(auto.get("default"), "true")

    def test_vm_os_variant_default(self):
        """VM OS variant has a default."""
        osv = self.parsed["variables"].get("vm_os_variant", {})
        self.assertIn("default", osv)


class TestOpenShiftClusterModule(unittest.TestCase):
    """Tests for the OpenShift Cluster module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "openshift", "cluster")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """OpenShift Cluster module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_cluster_resource(self):
        """OpenShift cluster resource exists."""
        self.assertIn("null_resource.openshift_cluster", self.parsed["resources"])

    def test_cluster_name_validation(self):
        """Cluster name has validation."""
        cn = self.parsed["variables"].get("cluster_name", {})
        self.assertIn("validation", cn)
        self.assertIn("regex", cn["validation"]["condition"])

    def test_base_domain_validation(self):
        """Base domain has validation."""
        bd = self.parsed["variables"].get("base_domain", {})
        self.assertIn("validation", bd)
        self.assertIn("regex", bd["validation"]["condition"])

    def test_cloud_provider_validation(self):
        """Cloud provider has validation."""
        cp = self.parsed["variables"].get("cloud_provider", {})
        self.assertIn("validation", cp)
        self.assertIn("aws", cp["validation"]["condition"])
        self.assertIn("azure", cp["validation"]["condition"])
        self.assertIn("gcp", cp["validation"]["condition"])

    def test_pull_secret_sensitive(self):
        """Pull secret is sensitive."""
        ps = self.parsed["variables"].get("pull_secret", {})
        self.assertTrue(ps.get("sensitive"))

    def test_cluster_outputs(self):
        """Cluster outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("cluster_name", outputs)
        self.assertIn("cluster_api_url", outputs)
        self.assertIn("cluster_console_url", outputs)
        self.assertIn("cluster_kubeconfig_path", outputs)
        self.assertIn("cluster_creds_path", outputs)

    def test_openshift_provider(self):
        """OpenShift provider is declared."""
        providers = self.parsed["terraform_config"].get("required_providers", {})
        self.assertIn("openshift", providers)
        self.assertEqual(providers["openshift"]["source"], "openshift/openshift")

    def test_additional_install_flags(self):
        """Additional install flags are supported."""
        self.assertIn("additional_install_flags", self.parsed["variables"])


class TestOpenShiftDeploymentModule(unittest.TestCase):
    """Tests for the OpenShift Deployment module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "openshift", "deployment")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """OpenShift Deployment module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_config_map_resource(self):
        """ConfigMap resource exists."""
        self.assertIn("openshift_config_map.this", self.parsed["resources"])

    def test_secret_resource(self):
        """Secret resource exists."""
        self.assertIn("openshift_secret.this", self.parsed["resources"])

    def test_deployment_resource(self):
        """Deployment resource exists."""
        self.assertIn("openshift_deployment.this", self.parsed["resources"])

    def test_service_resource(self):
        """Service resource exists."""
        self.assertIn("openshift_service.this", self.parsed["resources"])

    def test_hpa_resource(self):
        """HPA resource exists."""
        self.assertIn("openshift_horizontal_pod_autoscaler.this", self.parsed["resources"])

    def test_pdb_resource(self):
        """PDB resource exists."""
        self.assertIn("openshift_pod_disruption_budget.this", self.parsed["resources"])

    def test_deployment_outputs(self):
        """Deployment outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("deployment_name", outputs)
        self.assertIn("deployment_namespace", outputs)
        self.assertIn("service_name", outputs)
        self.assertIn("service_cluster_ip", outputs)
        self.assertIn("config_map_name", outputs)
        self.assertIn("secret_name", outputs)
        self.assertIn("hpa_name", outputs)
        self.assertIn("pdb_name", outputs)

    def test_secret_data_sensitive(self):
        """Secret data is sensitive."""
        sd = self.parsed["variables"].get("secret_data", {})
        self.assertTrue(sd.get("sensitive"))

    def test_security_context(self):
        """Security context is configured."""
        resource = self.parsed["resources"]["openshift_deployment.this"]
        body = resource.get("body", "")
        self.assertIn("run_as_non_root", body)
        self.assertIn("allow_privilege_escalation", body)
        self.assertIn("read_only_root_filesystem", body)

    def test_probes_configured(self):
        """Liveness and readiness probes are configured."""
        resource = self.parsed["resources"]["openshift_deployment.this"]
        body = resource.get("body", "")
        self.assertIn("liveness_probe", body)
        self.assertIn("readiness_probe", body)

    def test_resource_limits(self):
        """Resource limits are configured."""
        resource = self.parsed["resources"]["openshift_deployment.this"]
        body = resource.get("body", "")
        self.assertIn("resources", body)
        self.assertIn("requests", body)
        self.assertIn("limits", body)

    def test_topology_spread_constraints(self):
        """Topology spread constraints are supported."""
        self.assertIn("topology_spread_constraints", self.parsed["variables"])

    def test_metrics_support(self):
        """Prometheus metrics are supported."""
        self.assertIn("enable_metrics", self.parsed["variables"])
        self.assertIn("metrics_path", self.parsed["variables"])


class TestOpenShiftProjectModule(unittest.TestCase):
    """Tests for the OpenShift Project module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "openshift", "project")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """OpenShift Project module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_project_resource(self):
        """Project resource exists."""
        self.assertIn("openshift_project.this", self.parsed["resources"])

    def test_resource_quota_resource(self):
        """Resource quota resource exists."""
        self.assertIn("openshift_resource_quota.this", self.parsed["resources"])

    def test_limit_range_resource(self):
        """Limit range resource exists."""
        self.assertIn("openshift_limit_range.this", self.parsed["resources"])

    def test_network_policy_resource(self):
        """Network policy resource exists."""
        self.assertIn("openshift_network_policy.this", self.parsed["resources"])

    def test_project_name_validation(self):
        """Project name has validation."""
        pn = self.parsed["variables"].get("name", {})
        self.assertIn("validation", pn)
        self.assertIn("regex", pn["validation"]["condition"])

    def test_project_outputs(self):
        """Project outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("project_name", outputs)
        self.assertIn("project_id", outputs)
        self.assertIn("quota_name", outputs)
        self.assertIn("limit_range_name", outputs)


class TestOpenShiftRBACModule(unittest.TestCase):
    """Tests for the OpenShift RBAC module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "openshift", "rbac")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """OpenShift RBAC module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_service_account_resource(self):
        """Service account resource exists."""
        self.assertIn("openshift_service_account.this", self.parsed["resources"])

    def test_role_resource(self):
        """Role resource exists."""
        self.assertIn("openshift_role.this", self.parsed["resources"])

    def test_cluster_role_resource(self):
        """Cluster role resource exists."""
        self.assertIn("openshift_cluster_role.this", self.parsed["resources"])

    def test_role_binding_resource(self):
        """Role binding resource exists."""
        self.assertIn("openshift_role_binding.this", self.parsed["resources"])

    def test_cluster_role_binding_resource(self):
        """Cluster role binding resource exists."""
        self.assertIn("openshift_cluster_role_binding.this", self.parsed["resources"])

    def test_additional_role_bindings(self):
        """Additional role bindings are supported."""
        self.assertIn("openshift_role_binding.additional", self.parsed["resources"])

    def test_automount_token_default(self):
        """Automount token defaults to false."""
        at = self.parsed["variables"].get("automount_token", {})
        self.assertEqual(at.get("default"), "false")

    def test_rbac_outputs(self):
        """RBAC outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("service_account_name", outputs)
        self.assertIn("service_account_namespace", outputs)
        self.assertIn("role_name", outputs)
        self.assertIn("cluster_role_name", outputs)
        self.assertIn("role_binding_name", outputs)
        self.assertIn("cluster_role_binding_name", outputs)


class TestOpenShiftRouteModule(unittest.TestCase):
    """Tests for the OpenShift Route module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "openshift", "route")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """OpenShift Route module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_route_resource(self):
        """Route resource exists."""
        self.assertIn("openshift_route.this", self.parsed["resources"])

    def test_tls_termination_validation(self):
        """TLS termination has validation."""
        tt = self.parsed["variables"].get("tls_termination", {})
        self.assertIn("validation", tt)
        self.assertIn("edge", tt["validation"]["condition"])
        self.assertIn("passthrough", tt["validation"]["condition"])
        self.assertIn("reencrypt", tt["validation"]["condition"])

    def test_insecure_policy_validation(self):
        """Insecure policy has validation."""
        ip = self.parsed["variables"].get("insecure_policy", {})
        self.assertIn("validation", ip)
        self.assertIn("Allow", ip["validation"]["condition"])
        self.assertIn("Disable", ip["validation"]["condition"])
        self.assertIn("Redirect", ip["validation"]["condition"])

    def test_wildcard_policy_validation(self):
        """Wildcard policy has validation."""
        wp = self.parsed["variables"].get("wildcard_policy", {})
        self.assertIn("validation", wp)
        self.assertIn("None", wp["validation"]["condition"])
        self.assertIn("Subdomain", wp["validation"]["condition"])

    def test_tls_certificate_sensitive(self):
        """TLS certificate is sensitive."""
        cert = self.parsed["variables"].get("tls_certificate", {})
        self.assertTrue(cert.get("sensitive"))

    def test_tls_key_sensitive(self):
        """TLS key is sensitive."""
        key = self.parsed["variables"].get("tls_key", {})
        self.assertTrue(key.get("sensitive"))

    def test_route_outputs(self):
        """Route outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("route_name", outputs)
        self.assertIn("route_namespace", outputs)
        self.assertIn("route_host", outputs)
        self.assertIn("route_path", outputs)
        self.assertIn("route_url", outputs)
        self.assertIn("route_tls_termination", outputs)


if __name__ == "__main__":
    unittest.main()
