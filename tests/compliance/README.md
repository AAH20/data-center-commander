# Data Center Commander — Compliance Validation Tests

This directory contains compliance validation tests for the Data Center Commander project. Tests are organized by policy engine.

## Directory Structure

```
tests/compliance/
├── conftest.py                    # Pytest configuration
├── opa/                           # OPA/Rego policy tests
│   ├── test_resource_tagging.py   # Resource tagging policy tests
│   ├── test_encryption.py         # Encryption policy tests
│   ├── test_network_segmentation.py # Network segmentation policy tests
│   ├── test_access_control.py     # Access control policy tests
│   └── test_compliance.py         # Compliance policy tests
├── sentinel/                      # Sentinel policy tests
│   └── test_sentinel_policies.py  # Sentinel policy validation tests
├── checkov/                       # Checkov policy tests
│   └── test_checkov_policies.py   # Checkov custom policy tests
└── tfsec/                         # tfsec rule tests
    └── test_tfsec_rules.py        # tfsec custom rule tests
```

## Running Tests

### Prerequisites

Install the required tools:

```bash
# OPA
brew install opa  # macOS
# or
curl -L -o opa https://openpolicyagent.org/downloads/latest/opa_darwin_amd64_static

# Sentinel
brew install sentinel  # macOS
# or
curl -L -o sentinel https://releases.hashicorp.com/sentinel/0.27.0/sentinel_0.27.0_darwin_amd64.zip

# Checkov
pip install checkov

# tfsec
brew install tfsec  # macOS
# or
curl -L -o tfsec https://github.com/aquasecurity/tfsec/releases/latest/download/tfsec-darwin-amd64
```

### Run All Tests

```bash
pytest tests/compliance/ -v
```

### Run Specific Test Suites

```bash
# OPA/Rego tests only
pytest tests/compliance/opa/ -v

# Sentinel tests only
pytest tests/compliance/sentinel/ -v

# Checkov tests only
pytest tests/compliance/checkov/ -v

# tfsec tests only
pytest tests/compliance/tfsec/ -v
```

### Run with Coverage

```bash
pytest tests/compliance/ --cov=policies --cov-report=html
```

## Test Coverage

### OPA/Rego Tests

- **Resource Tagging**: 60+ tests covering all required tags
- **Encryption**: 30+ tests covering encryption at rest, in transit, key management, certificates
- **Network Segmentation**: 60+ tests covering public/private segments, SSL/TLS, firewall, unused resources
- **Access Control**: 50+ tests covering MFA, least privilege, role-based access
- **Compliance**: 100+ tests covering assessments, management records, governance

### Sentinel Tests

- Policy file existence and format validation
- Mock data validation
- Framework availability checks

### Checkov Tests

- **Network Security**: 10 tests (DC_NET_001 through DC_NET_010)
- **Compute Security**: 10 tests (DC_COMPUTE_001 through DC_COMPUTE_010)
- **Storage Security**: 10 tests (DC_STORAGE_001 through DC_STORAGE_010)
- **Encryption**: 10 tests (DC_CRYPTO_001 through DC_CRYPTO_010)
- **IAM**: 10 tests (DC_IAM_001 through DC_IAM_010)
- **Logging & Monitoring**: 10 tests (DC_MONITOR_001 through DC_MONITOR_010)
- **Compliance & Governance**: 10 tests (DC_GOV_001 through DC_GOV_010)
- **Data Center Specific**: 10 tests (DC_DC_001 through DC_DC_010)

### tfsec Tests

- Rule file format validation
- Required field validation
- ID convention validation
- Severity level validation
- Category validation
- Network, encryption, IAM, and compliance rule presence checks

## Adding New Tests

1. Create a new test file in the appropriate subdirectory
2. Follow the existing test naming convention: `test_<policy_name>.py`
3. Use the existing test patterns and helper functions
4. Update this README with the new test information

## License

MIT
