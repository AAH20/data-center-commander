"""
Property-based testing for IaC fuzzing.

Uses hypothesis to generate property-based tests that verify
invariants across the entire input space.
"""

import json

from generators import (
    azure_policy_definition,
    azure_policy_parameter,
    policy_input,
    terraform_configuration,
    terraform_resource,
    terraform_variable,
    terraform_variables,
)
from hypothesis import HealthCheck, given, settings


class TestTerraformVariableProperties:
    """Property-based tests for Terraform variables."""

    @given(var=terraform_variable())
    def test_variable_name_is_non_empty_string(self, var):
        """Property: variable name is always a non-empty string."""
        assert isinstance(var["name"], str)
        assert len(var["name"]) > 0

    @given(var=terraform_variable())
    def test_variable_type_is_valid(self, var):
        """Property: variable type is always a valid Terraform type."""
        valid_types = ["string", "number", "bool", "list", "map", "object", "tuple", "set"]
        assert var["type"] in valid_types

    @given(var=terraform_variable())
    def test_variable_default_is_serializable(self, var):
        """Property: variable default is always JSON serializable."""
        json.dumps(var["default"])

    @given(var=terraform_variable())
    def test_variable_sensitive_is_boolean(self, var):
        """Property: sensitive flag is always boolean."""
        assert isinstance(var["sensitive"], bool)

    @given(var=terraform_variable())
    def test_variable_nullable_is_boolean(self, var):
        """Property: nullable flag is always boolean."""
        assert isinstance(var["nullable"], bool)

    @given(var=terraform_variable())
    def test_variable_description_is_string(self, var):
        """Property: description is always a string."""
        assert isinstance(var["description"], str)

    @given(vars=terraform_variables(min_vars=1, max_vars=100))
    def test_variables_list_is_non_empty(self, vars):
        """Property: variables list is always non-empty."""
        assert isinstance(vars, list)
        assert len(vars) >= 1

    @given(vars=terraform_variables(min_vars=1, max_vars=100))
    def test_all_variables_have_required_fields(self, vars):
        """Property: all variables have required fields."""
        for var in vars:
            assert "name" in var
            assert "type" in var
            assert "default" in var


class TestTerraformResourceProperties:
    """Property-based tests for Terraform resources."""

    @given(resource=terraform_resource())
    def test_resource_type_is_non_empty_string(self, resource):
        """Property: resource type is always a non-empty string."""
        assert isinstance(resource["type"], str)
        assert len(resource["type"]) > 0

    @given(resource=terraform_resource())
    def test_resource_name_is_non_empty_string(self, resource):
        """Property: resource name is always a non-empty string."""
        assert isinstance(resource["name"], str)
        assert len(resource["name"]) > 0

    @given(resource=terraform_resource())
    def test_resource_properties_is_dict(self, resource):
        """Property: resource properties is always a dict."""
        assert isinstance(resource["properties"], dict)

    @given(resource=terraform_resource())
    def test_resource_is_serializable(self, resource):
        """Property: resource is always JSON serializable."""
        json.dumps(resource)

    @given(config=terraform_configuration(min_resources=1, max_resources=20))
    @settings(suppress_health_check=list(HealthCheck))
    def test_configuration_has_required_fields(self, config):
        """Property: configuration has required fields."""
        assert "resources" in config
        assert "variables" in config
        assert "outputs" in config

    @given(config=terraform_configuration(min_resources=1, max_resources=20))
    @settings(suppress_health_check=list(HealthCheck))
    def test_configuration_resources_is_non_empty(self, config):
        """Property: configuration resources is always non-empty."""
        assert isinstance(config["resources"], list)
        assert len(config["resources"]) >= 1

    @given(config=terraform_configuration(min_resources=1, max_resources=20))
    @settings(suppress_health_check=list(HealthCheck))
    def test_configuration_is_serializable(self, config):
        """Property: configuration is always JSON serializable."""
        json.dumps(config)


class TestPolicyInputProperties:
    """Property-based tests for policy inputs."""

    @given(input_doc=policy_input())
    def test_policy_input_has_required_fields(self, input_doc):
        """Property: policy input has required fields."""
        assert "resource_id" in input_doc
        assert "environment" in input_doc
        assert "region" in input_doc
        assert "tags" in input_doc
        assert "encryption" in input_doc
        assert "network" in input_doc
        assert "access" in input_doc

    @given(input_doc=policy_input())
    def test_policy_input_resource_id_is_string(self, input_doc):
        """Property: resource_id is always a string."""
        assert isinstance(input_doc["resource_id"], str)

    @given(input_doc=policy_input())
    def test_policy_input_environment_is_string(self, input_doc):
        """Property: environment is always a string."""
        assert isinstance(input_doc["environment"], str)

    @given(input_doc=policy_input())
    def test_policy_input_region_is_string(self, input_doc):
        """Property: region is always a string."""
        assert isinstance(input_doc["region"], str)

    @given(input_doc=policy_input())
    def test_policy_input_tags_is_dict(self, input_doc):
        """Property: tags is always a dict."""
        assert isinstance(input_doc["tags"], dict)

    @given(input_doc=policy_input())
    def test_policy_input_encryption_is_dict(self, input_doc):
        """Property: encryption is always a dict."""
        assert isinstance(input_doc["encryption"], dict)

    @given(input_doc=policy_input())
    def test_policy_input_network_is_dict(self, input_doc):
        """Property: network is always a dict."""
        assert isinstance(input_doc["network"], dict)

    @given(input_doc=policy_input())
    def test_policy_input_access_is_dict(self, input_doc):
        """Property: access is always a dict."""
        assert isinstance(input_doc["access"], dict)

    @given(input_doc=policy_input())
    def test_policy_input_is_serializable(self, input_doc):
        """Property: policy input is always JSON serializable."""
        json.dumps(input_doc)

    @given(input_doc=policy_input())
    def test_encryption_at_rest_is_boolean(self, input_doc):
        """Property: encryption.at_rest is always boolean."""
        assert isinstance(input_doc["encryption"]["at_rest"], bool)

    @given(input_doc=policy_input())
    def test_encryption_in_transit_is_boolean(self, input_doc):
        """Property: encryption.in_transit is always boolean."""
        assert isinstance(input_doc["encryption"]["in_transit"], bool)

    @given(input_doc=policy_input())
    def test_network_segment_is_valid(self, input_doc):
        """Property: network.segment is always valid."""
        assert input_doc["network"]["segment"] in ["isolated", "restricted", "public"]

    @given(input_doc=policy_input())
    def test_access_mfa_is_boolean(self, input_doc):
        """Property: access.mfa is always boolean."""
        assert isinstance(input_doc["access"]["mfa"], bool)


class TestAzurePolicyProperties:
    """Property-based tests for Azure Policy."""

    @given(param=azure_policy_parameter())
    def test_parameter_has_required_fields(self, param):
        """Property: parameter has required fields."""
        assert "type" in param
        assert "metadata" in param
        assert "allowedValues" in param
        assert "defaultValue" in param

    @given(param=azure_policy_parameter())
    def test_parameter_type_is_valid(self, param):
        """Property: parameter type is always valid."""
        valid_types = ["String", "Array", "Object", "Boolean", "Integer", "Float", "DateTime"]
        assert param["type"] in valid_types

    @given(param=azure_policy_parameter())
    def test_parameter_metadata_is_dict(self, param):
        """Property: parameter metadata is always a dict."""
        assert isinstance(param["metadata"], dict)

    @given(param=azure_policy_parameter())
    def test_parameter_allowed_values_is_list(self, param):
        """Property: allowedValues is always a list."""
        assert isinstance(param["allowedValues"], list)

    @given(param=azure_policy_parameter())
    def test_parameter_is_serializable(self, param):
        """Property: parameter is always JSON serializable."""
        json.dumps(param)

    @given(policy=azure_policy_definition())
    def test_policy_has_required_fields(self, policy):
        """Property: policy has required fields."""
        assert "properties" in policy
        props = policy["properties"]
        assert "displayName" in props
        assert "description" in props
        assert "metadata" in props
        assert "parameters" in props
        assert "policyType" in props
        assert "mode" in props
        assert "policyRule" in props

    @given(policy=azure_policy_definition())
    def test_policy_type_is_valid(self, policy):
        """Property: policy type is always valid."""
        valid_types = ["BuiltIn", "Custom", "Static"]
        assert policy["properties"]["policyType"] in valid_types

    @given(policy=azure_policy_definition())
    def test_policy_mode_is_valid(self, policy):
        """Property: policy mode is always valid."""
        valid_modes = ["Indexed", "All", "Microsoft.DataPlane", "Microsoft.Kubernetes.DataPlane"]
        assert policy["properties"]["mode"] in valid_modes

    @given(policy=azure_policy_definition())
    def test_policy_rule_has_required_fields(self, policy):
        """Property: policy rule has required fields."""
        rule = policy["properties"]["policyRule"]
        assert "if" in rule
        assert "then" in rule

    @given(policy=azure_policy_definition())
    def test_policy_effect_is_valid(self, policy):
        """Property: policy effect is always valid."""
        valid_effects = [
            "Deny",
            "Audit",
            "Disabled",
            "Append",
            "DeployIfNotExists",
            "Modify",
            "AuditIfNotExists",
        ]
        assert policy["properties"]["policyRule"]["then"]["effect"] in valid_effects

    @given(policy=azure_policy_definition())
    def test_policy_is_serializable(self, policy):
        """Property: policy is always JSON serializable."""
        json.dumps(policy)


class TestCrossCuttingProperties:
    """Cross-cutting property-based tests."""

    @given(
        var=terraform_variable(),
        resource=terraform_resource(),
        input_doc=policy_input(),
    )
    def test_all_inputs_are_serializable(self, var, resource, input_doc):
        """Property: all inputs are JSON serializable."""
        json.dumps(var)
        json.dumps(resource)
        json.dumps(input_doc)

    @given(
        var=terraform_variable(),
        resource=terraform_resource(),
        input_doc=policy_input(),
    )
    def test_all_inputs_are_dicts(self, var, resource, input_doc):
        """Property: all inputs are dicts."""
        assert isinstance(var, dict)
        assert isinstance(resource, dict)
        assert isinstance(input_doc, dict)

    @given(
        var=terraform_variable(),
        resource=terraform_resource(),
        input_doc=policy_input(),
    )
    def test_all_inputs_have_required_fields(self, var, resource, input_doc):
        """Property: all inputs have required fields."""
        assert "name" in var
        assert "type" in resource
        assert "resource_id" in input_doc
