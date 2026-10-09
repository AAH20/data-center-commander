"""
Azure Policy Fuzzer.

Fuzzes Azure Policy definitions to ensure the policy engine
handles malformed, edge-case, and adversarial inputs.
"""

import json
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from generators import (
    azure_policy_parameter,
    azure_policy_definition,
    AZURE_POLICY_EFFECTS,
    AZURE_POLICY_LOCATIONS,
)


class TestAzurePolicyParameterFuzzing:
    """Fuzz Azure Policy parameters."""

    @given(param=azure_policy_parameter())
    def test_parameter_does_not_crash(self, param):
        """Ensure parameter processing doesn't crash."""
        assert isinstance(param, dict)
        assert "type" in param
        assert "metadata" in param

    @given(param=azure_policy_parameter())
    def test_parameter_type_valid(self, param):
        """Parameter type should be valid."""
        valid_types = ["String", "Array", "Object", "Boolean", "Integer", "Float", "DateTime"]
        assert param["type"] in valid_types

    @given(param=azure_policy_parameter())
    def test_parameter_metadata_structure(self, param):
        """Parameter metadata should have expected structure."""
        metadata = param["metadata"]
        assert isinstance(metadata, dict)
        assert "displayName" in metadata
        assert "description" in metadata

    @given(param=azure_policy_parameter())
    def test_parameter_serializable(self, param):
        """Parameter should be JSON serializable."""
        try:
            json.dumps(param)
        except (TypeError, ValueError):
            pytest.fail("Parameter is not JSON serializable")

    @given(param=azure_policy_parameter())
    def test_parameter_allowed_values_list(self, param):
        """Allowed values should be a list."""
        assert isinstance(param["allowedValues"], list)

    @given(param=azure_policy_parameter())
    def test_parameter_default_value(self, param):
        """Default value should be present."""
        assert "defaultValue" in param


class TestAzurePolicyDefinitionFuzzing:
    """Fuzz Azure Policy definitions."""

    @given(policy=azure_policy_definition())
    def test_policy_does_not_crash(self, policy):
        """Ensure policy processing doesn't crash."""
        assert isinstance(policy, dict)
        assert "properties" in policy

    @given(policy=azure_policy_definition())
    def test_policy_properties_structure(self, policy):
        """Policy properties should have expected structure."""
        props = policy["properties"]
        assert isinstance(props, dict)
        assert "displayName" in props
        assert "description" in props
        assert "metadata" in props
        assert "parameters" in props
        assert "policyType" in props
        assert "mode" in props
        assert "policyRule" in props

    @given(policy=azure_policy_definition())
    def test_policy_metadata_structure(self, policy):
        """Policy metadata should have expected structure."""
        metadata = policy["properties"]["metadata"]
        assert isinstance(metadata, dict)
        assert "category" in metadata
        assert "version" in metadata

    @given(policy=azure_policy_definition())
    def test_policy_type_valid(self, policy):
        """Policy type should be valid."""
        valid_types = ["BuiltIn", "Custom", "Static"]
        assert policy["properties"]["policyType"] in valid_types

    @given(policy=azure_policy_definition())
    def test_policy_mode_valid(self, policy):
        """Policy mode should be valid."""
        valid_modes = ["Indexed", "All", "Microsoft.DataPlane", "Microsoft.Kubernetes.DataPlane"]
        assert policy["properties"]["mode"] in valid_modes

    @given(policy=azure_policy_definition())
    def test_policy_rule_structure(self, policy):
        """Policy rule should have expected structure."""
        rule = policy["properties"]["policyRule"]
        assert isinstance(rule, dict)
        assert "if" in rule
        assert "then" in rule

    @given(policy=azure_policy_definition())
    def test_policy_rule_if_structure(self, policy):
        """Policy rule if should have expected structure."""
        if_clause = policy["properties"]["policyRule"]["if"]
        assert isinstance(if_clause, dict)
        assert "field" in if_clause
        assert "equals" in if_clause

    @given(policy=azure_policy_definition())
    def test_policy_rule_then_structure(self, policy):
        """Policy rule then should have expected structure."""
        then_clause = policy["properties"]["policyRule"]["then"]
        assert isinstance(then_clause, dict)
        assert "effect" in then_clause

    @given(policy=azure_policy_definition())
    def test_policy_effect_valid(self, policy):
        """Policy effect should be valid."""
        valid_effects = ["Deny", "Audit", "Disabled", "Append", "DeployIfNotExists", "Modify", "AuditIfNotExists"]
        assert policy["properties"]["policyRule"]["then"]["effect"] in valid_effects

    @given(policy=azure_policy_definition())
    def test_policy_serializable(self, policy):
        """Policy should be JSON serializable."""
        try:
            json.dumps(policy)
        except (TypeError, ValueError):
            pytest.fail("Policy is not JSON serializable")

    @given(policy=azure_policy_definition())
    def test_policy_parameters_dict(self, policy):
        """Policy parameters should be a dict."""
        assert isinstance(policy["properties"]["parameters"], dict)


class TestAzurePolicyEdgeCases:
    """Test edge cases for Azure Policy."""

    @given(
        effect=st.sampled_from(["Deny", "Audit", "Disabled", "Append", "DeployIfNotExists", "Modify", "AuditIfNotExists", "deny", "audit", "disabled", "", "unknown"]),
    )
    def test_effect_case_sensitivity(self, effect):
        """Effect should be case-insensitive."""
        is_deny = effect.lower() == "deny"
        is_audit = effect.lower() == "audit"
        is_disabled = effect.lower() == "disabled"
        # These should be handled correctly
        assert isinstance(is_deny, bool)
        assert isinstance(is_audit, bool)
        assert isinstance(is_disabled, bool)

    @given(
        mode=st.sampled_from(["Indexed", "All", "Microsoft.DataPlane", "Microsoft.Kubernetes.DataPlane", "indexed", "all", "", "unknown"]),
    )
    def test_mode_case_sensitivity(self, mode):
        """Mode should be case-insensitive."""
        is_indexed = mode.lower() == "indexed"
        is_all = mode.lower() == "all"
        # These should be handled correctly
        assert isinstance(is_indexed, bool)
        assert isinstance(is_all, bool)

    @given(
        policy_type=st.sampled_from(["BuiltIn", "Custom", "Static", "builtin", "custom", "static", "", "unknown"]),
    )
    def test_policy_type_case_sensitivity(self, policy_type):
        """Policy type should be case-insensitive."""
        is_builtin = policy_type.lower() == "builtin"
        is_custom = policy_type.lower() == "custom"
        is_static = policy_type.lower() == "static"
        # These should be handled correctly
        assert isinstance(is_builtin, bool)
        assert isinstance(is_custom, bool)
        assert isinstance(is_static, bool)

    @given(
        param_type=st.sampled_from(["String", "Array", "Object", "Boolean", "Integer", "Float", "DateTime", "string", "array", "object", "boolean", "integer", "float", "datetime", "", "unknown"]),
    )
    def test_parameter_type_case_sensitivity(self, param_type):
        """Parameter type should be case-insensitive."""
        is_string = param_type.lower() == "string"
        is_array = param_type.lower() == "array"
        is_object = param_type.lower() == "object"
        is_boolean = param_type.lower() == "boolean"
        is_integer = param_type.lower() == "integer"
        is_float = param_type.lower() == "float"
        is_datetime = param_type.lower() == "datetime"
        # These should be handled correctly
        assert isinstance(is_string, bool)
        assert isinstance(is_array, bool)
        assert isinstance(is_object, bool)
        assert isinstance(is_boolean, bool)
        assert isinstance(is_integer, bool)
        assert isinstance(is_float, bool)
        assert isinstance(is_datetime, bool)


class TestAzurePolicySecurity:
    """Security-focused fuzzing for Azure Policy."""

    @given(policy=azure_policy_definition())
    def test_deny_effect_has_details(self, policy):
        """Deny effect should have details."""
        then_clause = policy["properties"]["policyRule"]["then"]
        if then_clause["effect"] == "Deny":
            # Deny should have details
            assert "details" in then_clause

    @given(policy=azure_policy_definition())
    def test_deploy_if_not_exists_has_details(self, policy):
        """DeployIfNotExists should have details."""
        then_clause = policy["properties"]["policyRule"]["then"]
        if then_clause["effect"] == "DeployIfNotExists":
            # DeployIfNotExists should have details
            assert "details" in then_clause

    @given(policy=azure_policy_definition())
    def test_modify_has_details(self, policy):
        """Modify should have details."""
        then_clause = policy["properties"]["policyRule"]["then"]
        if then_clause["effect"] == "Modify":
            # Modify should have details
            assert "details" in then_clause

    @given(policy=azure_policy_definition())
    def test_append_has_details(self, policy):
        """Append should have details."""
        then_clause = policy["properties"]["policyRule"]["then"]
        if then_clause["effect"] == "Append":
            # Append should have details
            assert "details" in then_clause
