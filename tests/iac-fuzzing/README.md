# IaC Fuzzing Suite

Comprehensive fuzzing suite for Data Center Commander IaC inputs. Tests Terraform variables, policy inputs, and configurations against the policy engine to find crashes, hangs, and unexpected behavior.

## Structure

```
tests/iac-fuzzing/
├── __init__.py
├── conftest.py                           # Pytest fixtures and hypothesis profiles
├── generators.py                         # Hypothesis strategies and random generators
├── fuzz_atheris.py                       # Atheris fuzz targets
├── run_fuzzing.py                        # Fuzzing runner script
├── requirements.txt                      # Dependencies
├── test_terraform_variable_fuzzing.py    # Terraform variable fuzzing tests
├── test_policy_fuzzing.py                # Policy input fuzzing tests
├── test_configuration_fuzzing.py         # Configuration fuzzing tests
├── test_policy_engine_fuzzer.py          # Policy engine fuzzer
├── test_azure_policy_fuzzer.py           # Azure Policy fuzzer
├── test_rego_policy_fuzzer.py            # Rego policy fuzzer
├── test_checkov_policy_fuzzer.py         # Checkov policy fuzzer
└── test_property_based.py                # Property-based tests
```

## Quick Start

### Install Dependencies

```bash
pip install -r tests/iac-fuzzing/requirements.txt
```

### Run All Tests

```bash
# Run with default profile (1000 examples per test)
python tests/iac-fuzzing/run_fuzzing.py

# Run with CI profile (100 examples per test)
python tests/iac-fuzzing/run_fuzzing.py --ci

# Run with dev profile (10 examples per test)
python tests/iac-fuzzing/run_fuzzing.py --dev

# Run with coverage
python tests/iac-fuzzing/run_fuzzing.py --coverage

# Run with verbose output
python tests/iac-fuzzing/run_fuzzing.py --verbose
```

### Run Specific Test Modules

```bash
# Terraform variable fuzzing
pytest tests/iac-fuzzing/test_terraform_variable_fuzzing.py -v

# Policy input fuzzing
pytest tests/iac-fuzzing/test_policy_fuzzing.py -v

# Configuration fuzzing
pytest tests/iac-fuzzing/test_configuration_fuzzing.py -v

# Policy engine fuzzer
pytest tests/iac-fuzzing/test_policy_engine_fuzzer.py -v

# Azure Policy fuzzer
pytest tests/iac-fuzzing/test_azure_policy_fuzzer.py -v

# Rego policy fuzzer
pytest tests/iac-fuzzing/test_rego_policy_fuzzer.py -v

# Checkov policy fuzzer
pytest tests/iac-fuzzing/test_checkov_policy_fuzzer.py -v

# Property-based tests
pytest tests/iac-fuzzing/test_property_based.py -v
```

### Run Atheris Fuzzer

```bash
# Run atheris fuzzer with 10000 iterations
python tests/iac-fuzzing/run_fuzzing.py --atheris --runs 10000

# Or directly
python -m atheris tests/iac-fuzzing/fuzz_atheris.py -atheris_runs=10000
```

## Test Modules

### Terraform Variable Fuzzing (`test_terraform_variable_fuzzing.py`)

Fuzzes Terraform variable definitions to ensure the policy engine handles:
- Malformed variable names
- Invalid variable types
- Edge-case default values
- Sensitive variable names
- Deeply nested structures
- Very long strings

### Policy Input Fuzzing (`test_policy_fuzzing.py`)

Fuzzes policy input documents for Rego/Checkov evaluation:
- Resource IDs
- Environments
- Regions
- Tags
- Encryption settings
- Network settings
- Access settings
- Retention settings
- Backup settings
- Monitoring settings
- Logging settings
- Certificate settings
- License settings
- Support settings

### Configuration Fuzzing (`test_configuration_fuzzing.py`)

Fuzzes complete Terraform configurations:
- Resource types
- Resource names
- Resource properties
- Multiple resources
- Variables
- Outputs
- Provider settings
- Terraform version

### Policy Engine Fuzzer (`test_policy_engine_fuzzer.py`)

Fuzzes the policy engine directly:
- Encryption policy evaluation
- Network policy evaluation
- Access policy evaluation
- Compliance policy evaluation
- Tagging policy evaluation
- Certificate policy evaluation
- License policy evaluation
- Support policy evaluation

### Azure Policy Fuzzer (`test_azure_policy_fuzzer.py`)

Fuzzes Azure Policy definitions:
- Policy parameters
- Policy metadata
- Policy rules
- Policy effects
- Policy modes
- Policy types

### Rego Policy Fuzzer (`test_rego_policy_fuzzer.py`)

Fuzzes Rego policy inputs:
- Encryption rules
- Network rules
- Access rules
- Compliance rules
- Tagging rules

### Checkov Policy Fuzzer (`test_checkov_policy_fuzzer.py`)

Fuzzes Checkov policy inputs:
- Encryption checks
- Network checks
- IAM checks
- Monitoring checks
- Backup checks

### Property-Based Tests (`test_property_based.py`)

Property-based tests using hypothesis:
- Terraform variable properties
- Terraform resource properties
- Policy input properties
- Azure Policy properties
- Cross-cutting properties

## Hypothesis Profiles

The suite uses three hypothesis profiles:

- **fuzzing** (default): 1000 examples per test
- **ci**: 100 examples per test
- **dev**: 10 examples per test

Profiles can be set via:
- `conftest.py` (default)
- `--hypothesis-profile` pytest option
- `HYPOTHESIS_PROFILE` environment variable

## Atheris Fuzzer

The atheris fuzzer (`fuzz_atheris.py`) provides three fuzz targets:

- `TestOneInput`: Generic fuzz target
- `TestOneInput_TerraformVariable`: Terraform variable fuzzer
- `TestOneInput_PolicyInput`: Policy input fuzzer
- `TestOneInput_TerraformResource`: Terraform resource fuzzer

Run with:
```bash
python -m atheris tests/iac-fuzzing/fuzz_atheris.py -atheris_runs=10000
```

## Generators

The `generators.py` module provides:

### Hypothesis Strategies

- `terraform_variable()`: Terraform variable definition
- `terraform_variables()`: List of Terraform variables
- `terraform_resource()`: Terraform resource configuration
- `terraform_configuration()`: Complete Terraform configuration
- `policy_input()`: Policy input document
- `azure_policy_parameter()`: Azure Policy parameter
- `azure_policy_definition()`: Azure Policy definition

### Random Generators (for atheris)

- `random_terraform_variable_dict()`: Random Terraform variable dict
- `random_policy_input_dict()`: Random policy input dict
- `random_terraform_resource_dict()`: Random Terraform resource dict

## Coverage

Run with coverage:
```bash
python tests/iac-fuzzing/run_fuzzing.py --coverage
```

This generates:
- Terminal coverage report
- HTML coverage report in `htmlcov/`

## CI Integration

Add to your CI pipeline:

```yaml
# .github/workflows/fuzzing.yml
name: IaC Fuzzing

on: [push, pull_request]

jobs:
  fuzzing:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install -r tests/iac-fuzzing/requirements.txt
      - run: python tests/iac-fuzzing/run_fuzzing.py --ci
```

## Findings

The fuzzing suite may find:
- Crashes (unhandled exceptions)
- Hangs (infinite loops)
- Unexpected behavior (wrong results)
- Security issues (sensitive data exposure)
- Performance issues (slow evaluation)

When a finding is found, hypothesis will shrink the input to the minimal reproducer and save it in `.hypothesis/`.

## License

Same as Data Center Commander.
