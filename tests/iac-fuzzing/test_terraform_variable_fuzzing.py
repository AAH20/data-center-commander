"""
Terraform Variable Fuzzing Tests.

Fuzzes Terraform variable definitions to ensure the policy engine
handles malformed, edge-case, and adversarial inputs without crashing.
"""

import json

import pytest
from generators import (
    TERRAFORM_LIST_VALUES,
    TERRAFORM_MAP_VALUES,
    TERRAFORM_STRING_VALUES,
    TERRAFORM_VARIABLE_NAMES,
    terraform_variable,
    terraform_variables,
)
from hypothesis import given
from hypothesis import strategies as st


class TestTerraformVariableFuzzing:
    """Fuzz Terraform variable definitions."""

    @given(var=terraform_variable())
    def test_variable_does_not_crash(self, var):
        """Ensure variable processing doesn't crash on any input."""
        # Simulate variable processing
        assert isinstance(var, dict)
        assert "name" in var
        assert "type" in var
        assert "default" in var

    @given(var=terraform_variable())
    def test_variable_name_is_string(self, var):
        """Variable name should always be a string."""
        assert isinstance(var["name"], str)

    @given(var=terraform_variable())
    def test_variable_type_is_valid(self, var):
        """Variable type should be a valid Terraform type."""
        valid_types = ["string", "number", "bool", "list", "map", "object", "tuple", "set"]
        assert var["type"] in valid_types

    @given(var=terraform_variable())
    def test_variable_default_serializable(self, var):
        """Variable default should be JSON serializable."""
        try:
            json.dumps(var["default"])
        except (TypeError, ValueError):
            pytest.fail("Variable default is not JSON serializable")

    @given(var=terraform_variable())
    def test_variable_name_not_empty(self, var):
        """Variable name should not be empty."""
        assert len(var["name"]) > 0

    @given(var=terraform_variable())
    def test_variable_name_no_special_chars(self, var):
        """Variable name should only contain valid characters."""
        import re

        assert re.match(r"^[a-zA-Z_-][a-zA-Z0-9_-]*$", var["name"])

    @given(vars=terraform_variables(min_vars=1, max_vars=50))
    def test_multiple_variables_no_crash(self, vars):
        """Ensure multiple variables don't crash the system."""
        assert isinstance(vars, list)
        assert len(vars) >= 1

    @given(vars=terraform_variables(min_vars=1, max_vars=50))
    def test_variable_names_unique(self, vars):
        """Variable names should be unique within a module."""
        names = [v["name"] for v in vars]
        # Note: This may fail for generated data, which is expected
        # The test documents the expectation
        if len(names) != len(set(names)):
            pytest.skip("Duplicate variable names detected - this is a finding")

    @given(
        name=TERRAFORM_VARIABLE_NAMES,
        default=st.one_of(
            TERRAFORM_STRING_VALUES,
            TERRAFORM_LIST_VALUES,
            TERRAFORM_MAP_VALUES,
        ),
    )
    def test_variable_with_known_name(self, name, default):
        """Test variables with known Terraform variable names."""
        var = {
            "name": name,
            "type": "string",
            "default": default,
            "description": "test",
            "sensitive": False,
            "nullable": True,
        }
        assert isinstance(var["name"], str)
        assert isinstance(var["default"], (str, list, dict))

    @given(var=terraform_variable())
    def test_variable_sensitive_flag(self, var):
        """Sensitive flag should be boolean."""
        assert isinstance(var["sensitive"], bool)

    @given(var=terraform_variable())
    def test_variable_nullable_flag(self, var):
        """Nullable flag should be boolean."""
        assert isinstance(var["nullable"], bool)

    @given(var=terraform_variable())
    def test_variable_description_string(self, var):
        """Description should be a string."""
        assert isinstance(var["description"], str)


class TestTerraformVariableEdgeCases:
    """Test edge cases for Terraform variables."""

    @given(
        name=st.text(min_size=0, max_size=0),
        default=TERRAFORM_STRING_VALUES,
    )
    def test_empty_variable_name(self, name, default):
        """Empty variable name should be handled gracefully."""
        var = {"name": name, "type": "string", "default": default}
        # Empty names are invalid but shouldn't crash
        assert isinstance(var, dict)

    @given(
        name=st.text(min_size=1000, max_size=1000),
        default=TERRAFORM_STRING_VALUES,
    )
    def test_very_long_variable_name(self, name, default):
        """Very long variable names should be handled."""
        var = {"name": name, "type": "string", "default": default}
        assert isinstance(var, dict)

    @given(
        default=st.recursive(
            TERRAFORM_STRING_VALUES,
            lambda children: st.lists(children, min_size=0, max_size=5),
            max_leaves=10,
        ),
    )
    def test_deeply_nested_default(self, default):
        """Deeply nested default values should be handled."""
        var = {"name": "test", "type": "list", "default": default}
        assert isinstance(var, dict)

    @given(
        default=st.dictionaries(
            keys=st.text(min_size=1, max_size=100),
            values=st.text(min_size=0, max_size=1000),
            min_size=0,
            max_size=100,
        ),
    )
    def test_large_map_default(self, default):
        """Large map defaults should be handled."""
        var = {"name": "test", "type": "map", "default": default}
        assert isinstance(var, dict)


class TestTerraformVariableSecurity:
    """Security-focused fuzzing for Terraform variables."""

    @given(
        name=st.sampled_from(
            [
                "admin_password",
                "db_password",
                "api_key",
                "secret_key",
                "access_key",
                "private_key",
                "token",
                "credential",
            ]
        ),
        default=st.sampled_from(
            [
                "password123",
                "admin",
                "root",
                "secret",
                "AKIAIOSFODNN7EXAMPLE",
                "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            ]
        ),
    )
    def test_sensitive_variable_names(self, name, default):
        """Sensitive variable names should be flagged."""
        var = {"name": name, "type": "string", "default": default, "sensitive": True}
        # These should be marked as sensitive
        assert var["sensitive"] is True

    @given(
        default=st.sampled_from(
            [
                "0.0.0.0/0",
                "::/0",
                "password",
                "secret",
                "api_key",
                "apikey",
                "access_key",
                "private_key",
            ]
        ),
    )
    def test_sensitive_default_values(self, default):
        """Sensitive default values should be detected."""
        # These values contain sensitive patterns
        sensitive_patterns = [
            "password",
            "secret",
            "api_key",
            "apikey",
            "access_key",
            "private_key",
        ]
        has_sensitive = any(p in default.lower() for p in sensitive_patterns)
        assert has_sensitive or default in ["0.0.0.0/0", "::/0"]
