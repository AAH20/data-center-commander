# Azure Policy Initiatives — Data Center Commander

This directory contains Azure Policy Initiatives (Policy Sets) for data center compliance governance.

## Initiatives

| Initiative | File | Description |
|---|---|---|
| Data Center Security Baseline | `dce-security-baseline.json` | Core security controls for all data center resources |
| Data Center Regulatory Compliance | `dce-regulatory-compliance.json` | CIS, NIST 800-53, PCI-DSS, SOC 2, ISO 27001 |
| Data Center Data Protection | `dce-data-protection.json` | Encryption, backup, retention, and data lifecycle |
| Data Center Network Security | `dce-network-security.json` | NSG, firewall, private endpoint, DDoS policies |
| Data Center Identity & Access | `dce-identity-access.json` | RBAC, MFA, managed identity, PIM policies |
| Data Center Monitoring & Audit | `dce-monitoring-audit.json` | Diagnostic settings, Log Analytics, Azure Monitor |
| Data Center Resource Governance | `dce-resource-governance.json` | Tagging, allowed locations, SKU restrictions |
| Data Center Disaster Recovery | `dce-disaster-recovery.json` | Backup, replication, availability zone policies |

## Deployment

### Azure CLI
```bash
# Create a policy initiative
az policy definition create \
  --name "dce-security-baseline" \
  --display-name "Data Center Security Baseline" \
  --description "Core security controls for data center resources" \
  --metadata category=Security \
  --rules policies/azure-policy/dce-security-baseline.json \
  --mode Indexed

# Assign to a management group or subscription
az policy assignment create \
  --name "dce-security-baseline-assignment" \
  --policy "dce-security-baseline" \
  --scope "/providers/Microsoft.Management/managementGroups/myMG" \
  --params '{ "effect": { "value": "Deny" } }'
```

### Terraform
```hcl
resource "azurerm_policy_definition" "dce_security_baseline" {
  name         = "dce-security-baseline"
  policy_type  = "Custom"
  mode         = "Indexed"
  display_name = "Data Center Security Baseline"
  description  = "Core security controls for data center resources"
  metadata     = jsonencode({ category = "Security" })
  policy_rule  = file("${path.module}/policies/azure-policy/dce-security-baseline.json")
}
```

### ARM Template
```json
{
  "type": "Microsoft.Authorization/policyDefinitions",
  "apiVersion": "2021-06-01",
  "name": "dce-security-baseline",
  "properties": {
    "displayName": "Data Center Security Baseline",
    "policyType": "Custom",
    "mode": "Indexed",
    "metadata": { "category": "Security" },
    "policyRule": "[json(loadTextContent('dce-security-baseline.json'))]"
  }
}
```

## Policy Modes

- **Indexed**: Applies to resource groups and resources (most common)
- **All**: Applies to all resource types including resource groups

## Effect Types

- **Deny**: Prevents non-compliant resource creation/modification
- **Audit**: Logs non-compliant resources (no enforcement)
- **DeployIfNotExists**: Deploys a remediation task
- **Modify**: Adds/updates tags or properties
- **AuditIfNotExists**: Checks for related resources
- **Disabled**: Policy is not evaluated

## Compliance Frameworks

These initiatives map to:
- **CIS Microsoft Azure Foundations Benchmark** v2.0
- **NIST SP 800-53** Rev. 5
- **PCI-DSS** v4.0
- **SOC 2** Type II
- **ISO/IEC 27001:2022**
- **Azure Security Benchmark** v3.0
