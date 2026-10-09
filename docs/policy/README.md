# Data Center Commander — Policy Framework Documentation

> **Version:** 1.0.0  
> **Last Updated:** September 2026  
> **Project:** Data Center Commander

---

## Overview

This directory contains comprehensive documentation for all policy frameworks used in the Data Center Commander project. These frameworks enforce governance, security, and compliance guardrails across multi-cloud infrastructure.

## Policy Frameworks

| Framework | Cloud | Documentation | Policy Location |
|-----------|-------|---------------|-----------------|
| **AWS Service Control Policies (SCPs)** | AWS | [aws-scps.md](aws-scps.md) | `policies/aws-scp/` |
| **Azure Policy Initiatives** | Azure | [azure-policy-initiatives.md](azure-policy-initiatives.md) | `policies/azure-policy/` |
| **GCP Organization Policies** | GCP | [gcp-organization-policies.md](gcp-organization-policies.md) | Terraform modules |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Data Center Commander                   │
│                  Policy Enforcement                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  AWS SCPs   │  │ Azure Policy│  │  GCP Org    │     │
│  │  (Ceiling)  │  │ Initiatives │  │  Policies   │     │
│  │             │  │ (7 Effects) │  │ (Boolean/   │     │
│  │             │  │             │  │  List)      │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│         │                │                │             │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐     │
│  │   OPA/Rego  │  │  Checkov    │  │  Terraform  │     │
│  │  (Universal)│  │  (IaC Scan) │  │  (Deployment)│    │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### AWS SCPs
```bash
# Deploy via AWS Organizations
aws organizations create-policy \
  --content file://policies/aws-scp/24-deny-iam-policy-modifications.json \
  --name "DenyIamPolicyModifications" \
  --type SERVICE_CONTROL_POLICY \
  --description "Prevents modification of IAM policies and roles"
```

### Azure Policy Initiatives
```bash
# Deploy via Azure CLI
az policy definition create \
  --name "dce-security-baseline" \
  --display-name "Data Center Security Baseline" \
  --rules policies/azure-policy/dce-security-baseline.json \
  --mode Indexed
```

### GCP Organization Policies
```bash
# Deploy via Terraform
terraform apply -var="org_id=organizations/123456789"
```

## Compliance Mapping

| Framework | CIS | NIST 800-53 | PCI-DSS | SOC 2 | ISO 27001 |
|-----------|-----|-------------|---------|-------|-----------|
| AWS SCPs | ✅ | ✅ | ✅ | ✅ | ✅ |
| Azure Policy | ✅ | ✅ | ✅ | ✅ | ✅ |
| GCP Org Policies | ✅ | ✅ | ✅ | ✅ | ✅ |
| OPA/Rego | ✅ | ✅ | ✅ | ✅ | ✅ |

## Related Documentation

- [Checkov Custom Policies](../../policies/checkov/README.md)
- [OPA/Rego Policies](../../policies/rego/)
- [Azure Policy Definitions](../../policies/azure-policy/README.md)
- [Policy-as-Code Matrix](../../../reports/policy-as-code-matrix.md)
