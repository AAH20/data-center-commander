# SOC Integration — Data Center Commander
# Trivy + OPA Container Security + Auto Scaling Integration
# Version: 2.0.0

## Overview

This directory contains the complete SOC (Security Operations Center) integration for Data Center Commander, using **Trivy** for container security scanning and **OPA (Open Policy Agent)** for policy enforcement.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Data Center Commander SOC                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │   Trivy      │    │    OPA       │    │   SOC        │                  │
│  │   Scanner    │───▶│   Policy     │───▶│   Alert      │                  │
│  │              │    │   Engine     │    │   Handler    │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│         │                   │                   │                          │
│         ▼                   ▼                   ▼                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │   Scan       │    │   Policy     │    │   Auto       │                  │
│  │   Reports    │    │   Evaluation │    │   Remediation│                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
security/soc/
├── trivy/                          # Trivy configuration and scripts
│   ├── trivy-config.yaml           # Trivy scan configuration
│   ├── trivy-scan.sh               # Trivy scan script
│   ├── trivy-report-template.tpl   # Report template
│   └── compliance/
│       └── dcc-baseline.yaml       # Custom compliance baseline
│
├── opa/                            # OPA policy configuration
│   ├── container-security.rego     # Container security policy
│   ├── autoscaling.rego            # Autoscaling security policy
│   ├── soc.rego                    # SOC integration policy
│   └── opa-config.yaml             # OPA server configuration
│
├── autoscaling/                    # Autoscaling security policies
│   └── autoscaling-policies.yaml   # HPA, VPA, PDB configurations
│
├── k8s/                            # Kubernetes manifests
│   └── k8s-security-manifests.yaml # K8s security resources
│
├── dashboards/                     # Monitoring dashboards
│   └── soc-dashboard.json          # Grafana dashboard
│
├── alerts/                         # Alert configurations
│   └── alert-rules.yaml            # Prometheus alert rules
│
├── runbooks/                       # Incident response runbooks
│   ├── critical-vulnerability.md   # Critical vulnerability runbook
│   ├── opa-policy-violation.md     # OPA policy violation runbook
│   └── autoscaling-security-event.md # Autoscaling security runbook
│
├── scripts/                        # Automation scripts
│   ├── soc-alert-handler.sh        # SOC alert handler
│   └── opa-policy-evaluator.sh     # OPA policy evaluator
│
└── soc/                            # SOC integration module
    ├── soc-integration.yaml        # SOC configuration
    ├── soc_integration.py          # Python integration module
    └── test_soc_integration.py     # Integration tests
```

## Quick Start

### 1. Install Trivy

```bash
# macOS
brew install trivy

# Linux
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin
```

### 2. Install OPA

```bash
# macOS
brew install opa

# Linux
curl -L -o opa https://openpolicyagent.org/downloads/latest/opa_linux_amd64_static
chmod +x opa
sudo mv opa /usr/local/bin/
```

### 3. Run Trivy Scan

```bash
# Scan a container image
./security/soc/trivy/trivy-scan.sh myimage:latest image

# Scan Kubernetes cluster
./security/soc/trivy/trivy-scan.sh "" k8s

# Scan filesystem
./security/soc/trivy/trivy-scan.sh /path/to/filesystem fs
```

### 4. Evaluate with OPA

```bash
# Evaluate container security policy
./security/soc/scripts/opa-policy-evaluator.sh container-security '{"image":"test:latest","vulnerabilities":{"critical":0,"high":0,"medium":0,"low":0}}'

# Evaluate Trivy scan results
./security/soc/scripts/opa-policy-evaluator.sh trivy-scan /var/log/trivy/report.json
```

### 5. Handle SOC Alerts

```bash
# Handle Trivy alert
./security/soc/scripts/soc-alert-handler.sh trivy /var/log/trivy/report.json

# Handle OPA alert
./security/soc/scripts/soc-alert-handler.sh opa '{"violations":["CRITICAL: Image has 1 critical vulnerabilities"],"image":"test:latest"}'
```

## Policy Configuration

### Container Security Policy

The container security policy (`opa/container-security.rego`) evaluates:

- **Vulnerability thresholds**: Maximum allowed vulnerabilities by severity
- **Misconfigurations**: Container configuration issues
- **Secrets**: Detected secrets in images
- **Registry**: Allowed container registries
- **Image integrity**: Digest, signature, SBOM, provenance
- **Runtime security**: Privileged mode, root user, capabilities
- **Network security**: Network policies, TLS
- **Resource limits**: CPU and memory limits
- **Health checks**: Liveness and readiness probes
- **Encryption**: At rest and in transit
- **Monitoring**: Metrics, logging, tracing
- **Autoscaling**: HPA, VPA, PDB

### Autoscaling Security Policy

The autoscaling security policy (`opa/autoscaling.rego`) evaluates:

- **Replica counts**: Minimum and maximum replicas
- **HPA/VPA**: Autoscaling configuration
- **PDB**: Pod disruption budgets
- **Resource targets**: CPU and memory utilization targets
- **Scaling policies**: Scale up/down policies
- **Scheduling**: Priority class, affinity, topology spread
- **Lifecycle**: Graceful shutdown, preStop hooks

### SOC Integration Policy

The SOC integration policy (`opa/soc.rego`) evaluates:

- **Alert severity**: Maps events to severity levels
- **Alert routing**: Determines notification channels
- **Auto-remediation**: Determines if auto-remediation should be attempted
- **Escalation**: Determines escalation level
- **Compliance**: Maps to compliance frameworks

## Compliance Frameworks

The integration supports the following compliance frameworks:

- **CIS Docker Benchmark**
- **CIS Kubernetes Benchmark**
- **NIST 800-53**
- **ISO 27001**
- **PCI DSS**
- **GDPR**
- **HIPAA**
- **SOC 2**

## Monitoring

### Grafana Dashboard

Import the dashboard from `dashboards/soc-dashboard.json` into Grafana.

### Prometheus Alerts

Deploy the alert rules from `alerts/alert-rules.yaml` to Prometheus.

## Auto-Remediation

The integration supports the following auto-remediation actions:

- **Rollback**: Rollback to previous version
- **Reschedule**: Reschedule to different node
- **Patch**: Apply security patch
- **Quarantine**: Quarantine affected pods
- **Scale down**: Scale down deployment

## Testing

Run the integration tests:

```bash
cd security/soc/soc
python -m pytest test_soc_integration.py -v
```

## References

- [Trivy Documentation](https://aquasecurity.github.io/trivy/)
- [OPA Documentation](https://www.openpolicyagent.org/docs/)
- [Gatekeeper Documentation](https://open-policy-agent.github.io/gatekeeper/)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [CIS Kubernetes Benchmark](https://www.cisecurity.org/benchmark/kubernetes)
- [NIST 800-53](https://csrc.nist.gov/projects/risk-management/sp800-53-controls/release-search#!/)
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
