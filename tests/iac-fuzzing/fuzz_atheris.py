"""
Atheris-based fuzzer for IaC inputs.

This module provides atheris-compatible fuzz targets for
Terraform variables, policy inputs, and IaC configurations.

Usage:
    python -m atheris fuzz_terraform_variables.py -atheris_runs=10000
    python -m atheris fuzz_policy_inputs.py -atheris_runs=10000
    python -m atheris fuzz_terraform_config.py -atheris_runs=10000
"""

import sys
import json
import atheris

with atheris.instrument_imports():
    from generators import (
        random_terraform_variable_dict,
        random_policy_input_dict,
        random_terraform_resource_dict,
    )


def TestOneInput(data):
    """Generic fuzz target that tries to parse input as JSON."""
    try:
        decoded = data.decode("utf-8", errors="ignore")
        parsed = json.loads(decoded)
        # Ensure it's a dict
        if not isinstance(parsed, dict):
            return
        # Try to process as different input types
        _process_as_terraform_variable(parsed)
        _process_as_policy_input(parsed)
        _process_as_terraform_resource(parsed)
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError, ValueError):
        pass


def _process_as_terraform_variable(data):
    """Process input as a Terraform variable."""
    if "name" in data and "type" in data:
        name = data["name"]
        var_type = data["type"]
        default = data.get("default")
        # Validate types
        assert isinstance(name, str)
        assert isinstance(var_type, str)
        # Try to serialize
        json.dumps(default)


def _process_as_policy_input(data):
    """Process input as a policy input."""
    if "resource_id" in data and "environment" in data:
        resource_id = data["resource_id"]
        environment = data["environment"]
        region = data.get("region")
        # Validate types
        assert isinstance(resource_id, str)
        assert isinstance(environment, str)
        # Try to serialize
        json.dumps(data)


def _process_as_terraform_resource(data):
    """Process input as a Terraform resource."""
    if "type" in data and "name" in data and "properties" in data:
        resource_type = data["type"]
        resource_name = data["name"]
        properties = data["properties"]
        # Validate types
        assert isinstance(resource_type, str)
        assert isinstance(resource_name, str)
        assert isinstance(properties, dict)
        # Try to serialize
        json.dumps(properties)


def TestOneInput_TerraformVariable(data):
    """Fuzz target for Terraform variables."""
    try:
        decoded = data.decode("utf-8", errors="ignore")
        parsed = json.loads(decoded)
        if isinstance(parsed, dict) and "name" in parsed:
            _process_as_terraform_variable(parsed)
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError, ValueError):
        pass


def TestOneInput_PolicyInput(data):
    """Fuzz target for policy inputs."""
    try:
        decoded = data.decode("utf-8", errors="ignore")
        parsed = json.loads(decoded)
        if isinstance(parsed, dict) and "resource_id" in parsed:
            _process_as_policy_input(parsed)
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError, ValueError):
        pass


def TestOneInput_TerraformResource(data):
    """Fuzz target for Terraform resources."""
    try:
        decoded = data.decode("utf-8", errors="ignore")
        parsed = json.loads(decoded)
        if isinstance(parsed, dict) and "type" in parsed and "properties" in parsed:
            _process_as_terraform_resource(parsed)
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError, ValueError):
        pass


def main():
    """Run the fuzzer."""
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
