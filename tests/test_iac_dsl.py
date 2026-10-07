"""Tests for IaC DSL: declarative infrastructure definition.

These tests verify that infrastructure can be defined declaratively,
validated, and compared for drift detection.
"""

from __future__ import annotations

import unittest

from dcc.iac.dsl import (
    ResourceType,
    ValidationError,
    define_resource,
    define_tenant,
)


class TestResourceDefinition(unittest.TestCase):
    """Test resource definition and validation."""

    def test_define_compute_resource(self):
        """Compute resource can be defined with CPU, RAM, GPU."""
        resource = define_resource(
            name="web-server-1",
            resource_type=ResourceType.COMPUTE,
            cpu_cores=4,
            memory_gb=16,
            gpu_units=0,
            power_kw=0.5,
            region="us-east-1",
        )
        self.assertEqual(resource.name, "web-server-1")
        self.assertEqual(resource.resource_type, ResourceType.COMPUTE)
        self.assertEqual(resource.cpu_cores, 4)
        self.assertEqual(resource.memory_gb, 16)

    def test_define_storage_resource(self):
        """Storage resource can be defined with capacity."""
        resource = define_resource(
            name="data-volume-1",
            resource_type=ResourceType.STORAGE,
            storage_tb=10,
            region="us-east-1",
        )
        self.assertEqual(resource.name, "data-volume-1")
        self.assertEqual(resource.resource_type, ResourceType.STORAGE)
        self.assertEqual(resource.storage_tb, 10)

    def test_define_network_resource(self):
        """Network resource can be defined with bandwidth."""
        resource = define_resource(
            name="vpc-1",
            resource_type=ResourceType.NETWORK,
            bandwidth_gbps=10,
            region="us-east-1",
        )
        self.assertEqual(resource.name, "vpc-1")
        self.assertEqual(resource.resource_type, ResourceType.NETWORK)
        self.assertEqual(resource.bandwidth_gbps, 10)

    def test_define_cooling_resource(self):
        """Cooling resource can be defined with capacity."""
        resource = define_resource(
            name="cooling-unit-1",
            resource_type=ResourceType.COOLING,
            cooling_kw=50,
            region="us-east-1",
        )
        self.assertEqual(resource.name, "cooling-unit-1")
        self.assertEqual(resource.resource_type, ResourceType.COOLING)
        self.assertEqual(resource.cooling_kw, 50)

    def test_invalid_resource_type_rejected(self):
        """Invalid resource type must be rejected."""
        with self.assertRaises(ValidationError):
            define_resource(
                name="bad-resource",
                resource_type="invalid",  # type: ignore
                region="us-east-1",
            )

    def test_negative_cpu_rejected(self):
        """Negative CPU cores must be rejected."""
        with self.assertRaises(ValidationError):
            define_resource(
                name="bad-compute",
                resource_type=ResourceType.COMPUTE,
                cpu_cores=-1,
                memory_gb=16,
                region="us-east-1",
            )

    def test_negative_memory_rejected(self):
        """Negative memory must be rejected."""
        with self.assertRaises(ValidationError):
            define_resource(
                name="bad-compute",
                resource_type=ResourceType.COMPUTE,
                cpu_cores=4,
                memory_gb=-1,
                region="us-east-1",
            )

    def test_empty_name_rejected(self):
        """Empty resource name must be rejected."""
        with self.assertRaises(ValidationError):
            define_resource(
                name="",
                resource_type=ResourceType.COMPUTE,
                cpu_cores=4,
                memory_gb=16,
                region="us-east-1",
            )

    def test_empty_region_rejected(self):
        """Empty region must be rejected."""
        with self.assertRaises(ValidationError):
            define_resource(
                name="test-resource",
                resource_type=ResourceType.COMPUTE,
                cpu_cores=4,
                memory_gb=16,
                region="",
            )


class TestInfrastructureDefinition(unittest.TestCase):
    """Test infrastructure definition and composition."""

    def test_define_tenant(self):
        """Tenant can be defined with resources."""
        tenant = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
                define_resource(
                    name="db-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=8,
                    memory_gb=32,
                    region="us-east-1",
                ),
            ],
        )
        self.assertEqual(tenant.name, "test-tenant")
        self.assertEqual(len(tenant.resources), 2)

    def test_tenant_total_capacity(self):
        """Tenant can compute total capacity."""
        tenant = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
                define_resource(
                    name="db-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=8,
                    memory_gb=32,
                    region="us-east-1",
                ),
            ],
        )
        self.assertEqual(tenant.total_cpu_cores, 12)
        self.assertEqual(tenant.total_memory_gb, 48)

    def test_tenant_empty_resources(self):
        """Tenant with no resources has zero capacity."""
        tenant = define_tenant(
            name="empty-tenant",
            region="us-east-1",
            resources=[],
        )
        self.assertEqual(tenant.total_cpu_cores, 0)
        self.assertEqual(tenant.total_memory_gb, 0)

    def test_resource_fingerprint(self):
        """Resource fingerprint is deterministic."""
        resource1 = define_resource(
            name="web-1",
            resource_type=ResourceType.COMPUTE,
            cpu_cores=4,
            memory_gb=16,
            region="us-east-1",
        )
        resource2 = define_resource(
            name="web-1",
            resource_type=ResourceType.COMPUTE,
            cpu_cores=4,
            memory_gb=16,
            region="us-east-1",
        )
        self.assertEqual(resource1.fingerprint, resource2.fingerprint)

    def test_resource_fingerprint_changes_with_config(self):
        """Resource fingerprint changes when config changes."""
        resource1 = define_resource(
            name="web-1",
            resource_type=ResourceType.COMPUTE,
            cpu_cores=4,
            memory_gb=16,
            region="us-east-1",
        )
        resource2 = define_resource(
            name="web-1",
            resource_type=ResourceType.COMPUTE,
            cpu_cores=8,
            memory_gb=16,
            region="us-east-1",
        )
        self.assertNotEqual(resource1.fingerprint, resource2.fingerprint)

    def test_tenant_fingerprint(self):
        """Tenant fingerprint is deterministic."""
        tenant1 = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        tenant2 = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        self.assertEqual(tenant1.fingerprint, tenant2.fingerprint)

    def test_drift_detection(self):
        """Drift is detected when desired state differs from actual."""
        desired = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        actual = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=8,  # Different from desired
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        self.assertTrue(desired.has_drift(actual))

    def test_no_drift_when_states_match(self):
        """No drift when desired and actual states match."""
        desired = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        actual = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        self.assertFalse(desired.has_drift(actual))


if __name__ == "__main__":
    unittest.main()


class TestResourceTypeStrEnumEdgeCases(unittest.TestCase):
    """Test ResourceType StrEnum edge cases."""

    def test_case_sensitive_resource_type(self):
        """ResourceType is case-sensitive: only exact matches work."""
        with self.assertRaises(ValidationError):
            define_resource(
                name="test-resource",
                resource_type="Compute",  # wrong case
                region="us-east-1",
            )

    def test_whitespace_prefix_resource_type_rejected(self):
        """ResourceType with leading whitespace is rejected."""
        with self.assertRaises(ValidationError):
            define_resource(
                name="test-resource",
                resource_type=" compute",
                region="us-east-1",
            )

    def test_whitespace_suffix_resource_type_rejected(self):
        """ResourceType with trailing whitespace is rejected."""
        with self.assertRaises(ValidationError):
            define_resource(
                name="test-resource",
                resource_type="compute ",
                region="us-east-1",
            )

    def test_empty_string_resource_type_rejected(self):
        """Empty string as resource_type is rejected."""
        with self.assertRaises(ValidationError):
            define_resource(
                name="test-resource",
                resource_type="",
                region="us-east-1",
            )

    def test_integer_like_string_resource_type_rejected(self):
        """Integer-like string as resource_type is rejected."""
        with self.assertRaises(ValidationError):
            define_resource(
                name="test-resource",
                resource_type="123",
                region="us-east-1",
            )

    def test_float_like_string_resource_type_rejected(self):
        """Float-like string as resource_type is rejected."""
        with self.assertRaises(ValidationError):
            define_resource(
                name="test-resource",
                resource_type="3.14",
                region="us-east-1",
            )

    def test_none_resource_type_rejected(self):
        """None as resource_type is rejected."""
        with self.assertRaises(ValidationError):
            define_resource(
                name="test-resource",
                resource_type=None,  # type: ignore
                region="us-east-1",
            )

    def test_resource_type_preserves_order(self):
        """ResourceType values maintain defined order."""
        values = [e.value for e in ResourceType]
        self.assertEqual(values, ["compute", "storage", "network", "cooling", "power"])

    def test_duplicate_resource_type_not_allowed(self):
        """Duplicate resource_type strings are allowed at runtime (StrEnum prevents at class def time)."""
        # StrEnum prevents duplicate values at class definition, but runtime usage allows
        # both "compute" lookups succeed since they map to the same enum member
        resource1 = define_resource(
            name="resource-1",
            resource_type="compute",
            region="us-east-1",
        )
        resource2 = define_resource(
            name="resource-2",
            resource_type="compute",
            region="us-east-1",
        )
        # Both resolve to the same ResourceType enum member
        self.assertEqual(resource1.resource_type, resource2.resource_type)
        self.assertEqual(resource1.resource_type.value, "compute")
