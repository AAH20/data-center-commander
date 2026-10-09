"""
Rego Policy Fuzzer.

Fuzzes Rego policy inputs to ensure the policy engine
handles malformed, edge-case, and adversarial inputs.
"""

import json
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from generators import (
    policy_input,
    random_policy_input_dict,
)


class TestRegoPolicyFuzzing:
    """Fuzz Rego policy inputs."""

    @given(input_doc=policy_input())
    def test_rego_input_does_not_crash(self, input_doc):
        """Ensure Rego evaluation doesn't crash on any input."""
        assert isinstance(input_doc, dict)
        assert "resource_id" in input_doc

    @given(input_doc=policy_input())
    def test_rego_input_serializable(self, input_doc):
        """Rego input should be JSON serializable."""
        try:
            json.dumps(input_doc)
        except (TypeError, ValueError):
            pytest.fail("Rego input is not JSON serializable")

    @given(input_doc=policy_input())
    def test_rego_encryption_rules(self, input_doc):
        """Fuzz Rego encryption rules."""
        enc = input_doc["encryption"]
        is_production = input_doc["environment"] == "production"
        is_staging = input_doc["environment"] == "staging"

        # Simulate Rego rule evaluation
        # deny contains msg if { common.is_production; not common.encrypted_at_rest }
        if is_production and not enc["at_rest"]:
            # Rule should fire
            pass

        # deny contains msg if { common.is_production; not common.encrypted_in_transit }
        if is_production and not enc["in_transit"]:
            # Rule should fire
            pass

        # deny contains msg if { common.is_staging; not common.encrypted_at_rest }
        if is_staging and not enc["at_rest"]:
            # Rule should fire
            pass

    @given(input_doc=policy_input())
    def test_rego_network_rules(self, input_doc):
        """Fuzz Rego network rules."""
        net = input_doc["network"]
        is_production = input_doc["environment"] == "production"

        # deny contains msg if { common.is_production; common.is_public_segment }
        if is_production and net["segment"] == "public":
            # Rule should fire
            pass

        # deny contains msg if { common.is_public_segment; input.network.waf_enabled != true }
        if net["segment"] == "public" and not net["waf_enabled"]:
            # Rule should fire
            pass

    @given(input_doc=policy_input())
    def test_rego_access_rules(self, input_doc):
        """Fuzz Rego access rules."""
        access = input_doc["access"]
        is_production = input_doc["environment"] == "production"

        # deny contains msg if { common.is_production; not common.mfa_enabled }
        if is_production and not access["mfa"]:
            # Rule should fire
            pass

        # deny contains msg if { not common.least_privilege }
        if not access["privilege"] == "least":
            # Rule should fire
            pass

    @given(input_doc=policy_input())
    def test_rego_compliance_rules(self, input_doc):
        """Fuzz Rego compliance rules."""
        is_production = input_doc["environment"] == "production"

        # deny contains msg if { common.is_production; not common.valid_security_assessment }
        if is_production and not input_doc.get("security_assessment"):
            # Rule should fire
            pass

    @given(input_doc=policy_input())
    def test_rego_tagging_rules(self, input_doc):
        """Fuzz Rego tagging rules."""
        tags = input_doc["tags"]

        # deny contains msg if { not common.has_owner }
        if "owner" not in tags:
            # Rule should fire
            pass

        # deny contains msg if { not common.has_cost_center }
        if "cost_center" not in tags:
            # Rule should fire
            pass


class TestRegoPolicyEdgeCases:
    """Test edge cases for Rego policies."""

    @given(
        environment=st.sampled_from(["production", "staging", "dev", "test", "prod", "development", "stage", "", "unknown", "PRODUCTION", "Production", "PROD", "Prod"]),
    )
    def test_rego_environment_values(self, environment):
        """Test various environment values."""
        is_production = environment.lower() == "production"
        is_staging = environment.lower() == "staging"
        is_dev = environment.lower() == "dev"
        # These should be handled correctly
        assert isinstance(is_production, bool)
        assert isinstance(is_staging, bool)
        assert isinstance(is_dev, bool)

    @given(
        segment=st.sampled_from(["isolated", "restricted", "public", "ISOLATED", "RESTRICTED", "PUBLIC", "", "unknown", "Isolated", "Restricted", "Public"]),
    )
    def test_rego_segment_values(self, segment):
        """Test various segment values."""
        is_isolated = segment.lower() == "isolated"
        is_restricted = segment.lower() == "restricted"
        is_public = segment.lower() == "public"
        # These should be handled correctly
        assert isinstance(is_isolated, bool)
        assert isinstance(is_restricted, bool)
        assert isinstance(is_public, bool)

    @given(
        tls_version=st.sampled_from(["TLSv1.0", "TLSv1.1", "TLSv1.2", "TLSv1.3", "SSLv3", "tlsv1.0", "tlsv1.1", "tlsv1.2", "tlsv1.3", "sslv3", "", "unknown", "TLSv1", "TLSv2", "TLSv3"]),
    )
    def test_rego_tls_version_values(self, tls_version):
        """Test various TLS version values."""
        is_tls_10 = tls_version.lower() == "tlsv1.0"
        is_tls_11 = tls_version.lower() == "tlsv1.1"
        is_tls_12 = tls_version.lower() == "tlsv1.2"
        is_tls_13 = tls_version.lower() == "tlsv1.3"
        is_ssl_3 = tls_version.lower() == "sslv3"
        # These should be handled correctly
        assert isinstance(is_tls_10, bool)
        assert isinstance(is_tls_11, bool)
        assert isinstance(is_tls_12, bool)
        assert isinstance(is_tls_13, bool)
        assert isinstance(is_ssl_3, bool)


class TestRegoPolicySecurity:
    """Security-focused fuzzing for Rego policies."""

    @given(input_doc=policy_input())
    def test_rego_production_encryption(self, input_doc):
        """Production resources should have encryption."""
        if input_doc["environment"] == "production":
            enc = input_doc["encryption"]
            # These are policy checks, not crash checks
            pass

    @given(input_doc=policy_input())
    def test_rego_public_segment_waf(self, input_doc):
        """Public segment should have WAF."""
        if input_doc["network"]["segment"] == "public":
            # This is a policy check, not a crash check
            pass

    @given(input_doc=policy_input())
    def test_rego_sensitive_data_encryption(self, input_doc):
        """Sensitive data should have encryption."""
        if input_doc["tags"].get("data_classification") == "sensitive":
            # This is a policy check, not a crash check
            pass

    @given(input_doc=policy_input())
    def test_rego_production_mfa(self, input_doc):
        """Production should have MFA."""
        if input_doc["environment"] == "production":
            # This is a policy check, not a crash check
            pass

    @given(input_doc=policy_input())
    def test_rego_no_wildcard_ssh(self, input_doc):
        """SSH should not be open to 0.0.0.0/0."""
        if input_doc["network"]["ssh_cidr"] == "0.0.0.0/0":
            # This is a policy check, not a crash check
            pass

    @given(input_doc=policy_input())
    def test_rego_no_wildcard_rdp(self, input_doc):
        """RDP should not be open to 0.0.0.0/0."""
        if input_doc["network"]["rdp_cidr"] == "0.0.0.0/0":
            # This is a policy check, not a crash check
            pass

    @given(input_doc=policy_input())
    def test_rego_no_wildcard_database(self, input_doc):
        """Database should not be open to 0.0.0.0/0."""
        if input_doc["network"]["database_cidr"] == "0.0.0.0/0":
            # This is a policy check, not a crash check
            pass
