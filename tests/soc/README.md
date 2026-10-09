# Data Center Commander — SOC + Auto Scaling + Container Test Suite

This directory contains security operations, auto-scaling, and container security tests for the Data Center Commander project.

## Directory Structure

```
tests/soc/
├── __init__.py                    # Package init
├── conftest.py                    # Shared fixtures and helpers
├── test_soc.py                    # SOC security tests
├── test_auto_scaling.py           # Auto Scaling (HPA/PDB) tests
├── test_container_security.py     # Container security tests
├── test_compliance.py             # Cross-cutting compliance tests
└── README.md                      # This file
```

## Test Suites

### SOC Tests (`test_soc.py`)

Security Operations Center tests validating the overall security posture:

- **Container Security**: Privileged mode, capabilities, root users, host namespaces, resource limits, image tags
- **Network Security**: Default-deny policies, namespace isolation, service exposure, ingress security
- **RBAC Security**: ServiceAccounts, ClusterRoles, wildcard permissions
- **Secrets & Config**: ConfigMap labeling, namespace placement
- **Pod Security**: Replica counts, labels, PVC usage, storage validation
- **Namespace Security**: Namespace existence, labels, resource placement

### Auto Scaling Tests (`test_auto_scaling.py`)

HorizontalPodAutoscaler and PodDisruptionBudget validation:

- **HPA Presence**: Existence, coverage, namespace, labels
- **HPA Configuration**: Replica bounds, CPU/memory metrics, target thresholds, API version
- **HPA Behavior**: Scale-up/down policies, stabilization windows, policy types
- **HPA Target Validation**: Target existence, API version
- **PDB Presence**: Existence, coverage, namespace, labels
- **PDB Configuration**: minAvailable, API version, selectors
- **Scaling Integration**: HPA+PDB coexistence, replica alignment

### Container Security Tests (`test_container_security.py`)

Deep container-level security validation:

- **Image Security**: Registry prefixes, floating tags, debug images
- **Runtime Security**: Privileged mode, capabilities, host paths, Docker socket
- **Volume Security**: Sensitive host paths, PVC validation
- **Environment Security**: Hardcoded secrets, valueFrom usage
- **Port Security**: Insecure ports, descriptive names
- **Init Container Security**: Privileged mode, resource limits
- **Health Probes**: HTTP/TCP checks, initial delays
- **Resource Security**: CPU/memory limits and requests

### Compliance Tests (`test_compliance.py`)

Cross-cutting compliance and governance:

- **Cross-Cutting Compliance**: Labels, namespace, HPA/PDB coverage, network policy coverage
- **Policy Enforcement**: OPA, Checkov, Sentinel, Azure policy existence
- **Documentation**: README, benchmarks, policy docs
- **Audit Trail**: Logging stack, log shippers, monitoring stack
- **Compliance Scope**: Namespace labels, owner labels, policy documentation

## Running Tests

### Prerequisites

```bash
pip install pyyaml pytest
```

### Run All SOC Tests

```bash
pytest tests/soc/ -v
```

### Run Specific Test Suites

```bash
# SOC tests only
pytest tests/soc/test_soc.py -v

# Auto Scaling tests only
pytest tests/soc/test_auto_scaling.py -v

# Container security tests only
pytest tests/soc/test_container_security.py -v

# Compliance tests only
pytest tests/soc/test_compliance.py -v
```

### Run with Coverage

```bash
pytest tests/soc/ --cov=tests/soc --cov-report=html
```

### Run Specific Test Class

```bash
pytest tests/soc/test_soc.py::TestContainerSecurity -v
```

### Run Specific Test

```bash
pytest tests/soc/test_soc.py::TestContainerSecurity::test_no_privileged_containers -v
```

## Test Fixtures

All test fixtures are defined in `conftest.py` and include:

| Fixture | Description |
|---------|-------------|
| `k8s_docs` | All Kubernetes manifests |
| `deployments` | All Deployment documents |
| `daemonsets` | All DaemonSet documents |
| `hpas` | All HorizontalPodAutoscaler documents |
| `pdbs` | All PodDisruptionBudget documents |
| `network_policies` | All NetworkPolicy documents |
| `services` | All Service documents |
| `configmaps` | All ConfigMap documents |
| `ingresses` | All Ingress documents |
| `rbac_docs` | All RBAC documents |
| `pvcs` | All PersistentVolumeClaim documents |
| `namespace` | The Namespace document |
| `all_pods` | All pod specs from workloads |

## Test Categories

### Hard Assertions (Must Pass)

These tests enforce security requirements that must be met:
- No privileged containers
- No dangerous capabilities
- No host PID/IPC sharing
- Resource limits and requests set
- No floating image tags
- Default-deny network policies exist
- Services use ClusterIP
- No wildcard RBAC permissions
- HPAs have CPU and memory metrics
- PDBs have minAvailable >= 1

### Documentation Tests (Always Pass)

These tests document the current security posture and flag gaps:
- `test_security_contexts_documented`
- `test_run_as_non_root_documented`
- `test_readonly_root_fs_documented`
- `test_capabilities_documented`

These tests always pass but serve as documentation of what containers have/don't have security contexts configured.

## License

MIT
