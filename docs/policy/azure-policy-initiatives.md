# Azure Policy Initiatives

> **Cloud:** Azure  
> **Policy Type:** Azure Policy Initiatives (Policy Sets)  
> **Location:** `policies/azure-policy/`

---

## Overview

Azure Policy is Azure's native governance service for enforcing organizational standards and assessing compliance at scale. It evaluates Azure resources against assigned policies and applies effects (deny, audit, modify, deploy, etc.) automatically.

An **Initiative** (also called a Policy Set) is a named, versioned, parameterized container of policy definitions. One assignment covers multiple policies, simplifying compliance management.

### Key Characteristics

| Attribute | Detail |
|-----------|--------|
| **Language** | JSON (ARM policy syntax) |
| **Scope** | Management Group, Subscription, Resource Group |
| **Effects** | Deny, Audit, AuditIfNotExists, Modify, DeployIfNotExists, Append, Disabled |
| **Evaluation** | Synchronous (request path) + Asynchronous (24h compliance scan) |
| **Remediation** | Built-in remediation tasks for existing resources |
| **Exemptions** | Policy exemptions with expiration dates |
| **Integration** | Microsoft Sentinel, Azure Monitor, Log Analytics |

---

## Policy Definition Syntax

Azure Policy uses ARM-compatible JSON:

```json
{
  "properties": {
    "displayName": "Require CostCenter tag on all resources",
    "policyType": "Custom",
    "mode": "Indexed",
    "metadata": {
      "category": "Tags",
      "version": "1.0.0"
    },
    "parameters": {
      "effect": {
        "type": "String",
        "defaultValue": "Deny",
        "allowedValues": ["Audit", "Deny", "Disabled"]
      }
    },
    "policyRule": {
      "if": {
        "allOf": [
          {
            "field": "type",
            "notEquals": "Microsoft.Resources/subscriptions/resourceGroups"
          },
          {
            "field": "tags.CostCenter",
            "exists": "false"
          }
        ]
      },
      "then": {
        "effect": "[parameters('effect')]"
      }
    }
  }
}
```

---

## The 7 Policy Effects

| Effect | Behavior | Use Case |
|--------|----------|----------|
| **Deny** | Blocks creation/update of non-compliant resources | Mandatory enforcement |
| **Audit** | Logs violations, allows deployment | Discovery before enforcement |
| **AuditIfNotExists** | Audits when related resources are missing | Detect VMs without Backup |
| **Modify** | Auto-adds tags, fixes properties | Auto-remediation (needs managed identity) |
| **DeployIfNotExists** | Auto-deploys missing related resources | Auto-configure Diagnostic Settings |
| **Append** | Auto-attaches properties to resources | Add Network ACLs to Storage |
| **Disabled** | Temporarily disables policy evaluation | Emergency exceptions |

### Evaluation Order

1. `disabled` checked first
2. `append` and `modify` evaluated (can alter the request)
3. `deny` evaluated (before audit to prevent double-logging)
4. `audit` evaluated
5. `manual` evaluated
6. `auditIfNotExists` evaluated
7. `denyAction` evaluated last
8. After Resource Provider success: `auditIfNotExists` and `deployIfNotExists` evaluated

---

## Data Center Commander Initiatives

### dce-security-baseline.json

**Purpose:** Core security controls for all data center resources. Covers encryption, network isolation, access control, and security monitoring.

**Compliance Mapping:**
- CIS Microsoft Azure Foundations Benchmark v2.0
- NIST SP 800-53 Rev. 5
- Azure Security Benchmark v3.0

**Parameters:**

| Parameter | Type | Default | Allowed Values | Description |
|-----------|------|---------|----------------|-------------|
| `effect` | String | `Deny` | `Deny`, `Audit`, `Disabled` | The effect of the policy |
| `allowedLocations` | Array | `["eastus", "westus2", "westeurope", "northeurope"]` | Any Azure regions | List of allowed Azure regions |
| `minimumTlsVersion` | String | `1.2` | `1.0`, `1.1`, `1.2` | Minimum TLS version for storage and web apps |

**Policy Definitions (48 total):**

| Category | Count | Reference IDs |
|----------|-------|---------------|
| Storage Security | 6 | `storageAccountsShouldUsePrivateLink`, `storageAccountsShouldRestrictNetworkAccess`, `storageAccountsShouldUseCustomerManagedKey`, `storageAccountsShouldHaveInfrastructureEncryption`, `storageAccountsShouldPreventSharedKeyAccess` |
| VM Security | 42 | `virtualMachinesShouldUseManagedDisks`, `virtualMachinesShouldHaveEndpointProtection`, `virtualMachinesShouldNotUseLegacyAuthentication`, `virtualMachinesShouldHaveAzureDiskEncryption`, `virtualMachinesShouldHaveVulnerabilityAssessment`, `virtualMachinesShouldHaveAdaptiveApplicationControls`, `virtualMachinesShouldHaveAdaptiveNetworkHardening`, `virtualMachinesShouldHaveJustInTimeNetworkAccess`, `virtualMachinesShouldHaveSecureBoot`, `virtualMachinesShouldHaveVtpm`, `virtualMachinesShouldHaveGuestAttestation`, `virtualMachinesShouldNotHavePublicIps`, `virtualMachinesShouldUseAvailabilityZones`, `virtualMachinesShouldUseProximityPlacementGroups`, `virtualMachinesShouldUseScaleSets`, `virtualMachinesShouldHavePatchAssessment`, `virtualMachinesShouldHaveAutomaticUpdates`, `virtualMachinesShouldHaveAntimalware`, `virtualMachinesShouldHaveSecurityCenterContact`, `virtualMachinesShouldHaveSecureBootAndVtpm`, `virtualMachinesShouldHaveConfidentialComputing`, `virtualMachinesShouldHaveDiskEncryptionSet`, `virtualMachinesShouldHaveKeyVaultIntegration`, `virtualMachinesShouldHavePrivateEndpoint`, `virtualMachinesShouldHaveNetworkWatcher`, `virtualMachinesShouldHaveFlowLogs`, `virtualMachinesShouldHaveDdosProtection`, `virtualMachinesShouldHaveWebApplicationFirewall`, `virtualMachinesShouldHaveAzureFirewall`, `virtualMachinesShouldHaveBastion`, `virtualMachinesShouldHaveJumpBox`, `virtualMachinesShouldHaveSessionRecording`, `virtualMachinesShouldHavePrivilegedAccess`, `virtualMachinesShouldHaveJustInTimeAccess`, `virtualMachinesShouldHaveTimeBoundAccess`, `virtualMachinesShouldHaveApprovalWorkflow` |

**Policy Groups:**

| Name | Category |
|------|----------|
| Data Center Security | Security |

---

## Planned Initiatives

The following initiatives are planned for future deployment:

| Initiative | File | Description |
|---|---|---|
| Data Center Regulatory Compliance | `dce-regulatory-compliance.json` | CIS, NIST 800-53, PCI-DSS, SOC 2, ISO 27001 |
| Data Center Data Protection | `dce-data-protection.json` | Encryption, backup, retention, and data lifecycle |
| Data Center Network Security | `dce-network-security.json` | NSG, firewall, private endpoint, DDoS policies |
| Data Center Identity & Access | `dce-identity-access.json` | RBAC, MFA, managed identity, PIM policies |
| Data Center Monitoring & Audit | `dce-monitoring-audit.json` | Diagnostic settings, Log Analytics, Azure Monitor |
| Data Center Resource Governance | `dce-resource-governance.json` | Tagging, allowed locations, SKU restrictions |
| Data Center Disaster Recovery | `dce-disaster-recovery.json` | Backup, replication, availability zone policies |

---

## Assignment Scope Hierarchy

```
Tenant Root Management Group
  └── Management Group (groups subscriptions by environment/department)
       └── Subscription (billing boundary)
            └── Resource Group (logical group)
                 └── Resource
```

Assignments cascade downward. **Best practice:** assign at the highest Management Group possible, never at subscription or resource group level.

---

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

resource "azurerm_management_group_policy_assignment" "dce_security_baseline" {
  name                 = "dce-security-baseline-assignment"
  policy_definition_id = azurerm_policy_definition.dce_security_baseline.id
  management_group_id  = var.management_group_id
  parameters = jsonencode({
    effect = { value = "Deny" }
  })
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

### Bicep

```bicep
resource policyDef 'Microsoft.Authorization/policyDefinitions@2023-04-01' = {
  name: 'dce-security-baseline'
  properties: {
    displayName: 'Data Center Security Baseline'
    policyType: 'Custom'
    mode: 'Indexed'
    metadata: { category: 'Security' }
    policyRule: json(loadTextContent('dce-security-baseline.json'))
  }
}
```

---

## Policy Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Indexed** | Applies to resource groups and resources | Most common; covers tags, locations, SKUs |
| **All** | Applies to all resource types including resource groups | Resource group-level policies |
| **Resource** | Applies to specific resource types | Targeted resource policies |

---

## Microsoft-Provided Initiatives

Azure provides built-in initiatives that can be used alongside custom initiatives:

| Initiative | Description |
|------------|-------------|
| **Microsoft Cloud Security Benchmark (MCSB)** | Successor to Azure Security Benchmark |
| **PCI DSS v3.2.1** | Payment Card Industry Data Security Standard |
| **ISO 27001:2013** | Information security management |
| **NIST SP 800-53** | National Institute of Standards and Technology |
| **HIPAA HITRUST** | Healthcare data protection |
| **Australian Government ISM** | Australian government security controls |

---

## Enterprise Azure Policy as Code (EPAC)

For managing Azure Policy at scale with CI/CD, use [EPAC](https://techcommunity.microsoft.com/t5/core-infrastructure-and-security/azure-enterprise-policy-as-code-a-new-approach/ba-p/3607843):

- Idempotent, desired-state deployments
- DRY principle (no repeated definitions)
- GitHub flow CI/CD integration
- Round-trip capability (extract existing environment)
- Coexistence of different teams owning different policy aspects

---

## Best Practices

### DO

- Assign initiatives at the highest Management Group level possible
- Use parameters to make policies reusable across environments
- Start with `Audit` effect, then graduate to `Deny` after validation
- Use `DeployIfNotExists` for auto-remediation of missing configurations
- Tag policies with metadata categories for organization
- Use policy exemptions with expiration dates for temporary exceptions
- Integrate with Microsoft Sentinel for security alerting

### DON'T

- Don't assign at subscription or resource group level (breaks inheritance)
- Don't use `Deny` without first running `Audit` to understand impact
- Don't forget that `deployIfNotExists` and `modify` require managed identity
- Don't exceed limits: 200 initiative definitions per scope, 2,500 per tenant, 500 policy definitions per scope
- Don't nest initiatives (flat structure only)
- Don't ignore the ~24h compliance scan cycle for audit effects

---

## Strengths

- Native Azure integration with synchronous enforcement in the ARM request path
- Rich effect model (7 effects covering detect, block, and auto-remediate)
- Built-in compliance dashboard and reporting
- Remediation tasks for existing non-compliant resources
- Policy exemptions with expiration dates
- Integration with Microsoft Sentinel for security alerting
- Bicep/Terraform native support

## Limitations

- Azure-only (no multi-cloud coverage)
- JSON policy syntax is verbose and complex
- `deployIfNotExists` and `modify` require managed identity configuration
- Compliance scan runs ~24h cycle (not real-time for audit effects)
- Initiative nesting is not supported (flat structure only)
- Limits: 200 initiative definitions per scope, 2,500 per tenant, 500 policy definitions per scope

---

## Compliance Mapping

| Framework | Controls |
|-----------|----------|
| **CIS Azure Foundations v2.0** | 1.1–1.3, 2.1–2.12, 3.1–3.11, 4.1–4.5, 5.1–5.5, 6.1–6.7, 7.1–7.5, 8.1–8.5, 9.1–9.11 |
| **NIST SP 800-53 Rev. 5** | AC-2, AC-3, AC-5, AC-6, AC-16, AU-6, AU-9, CM-3, CM-5, IA-2, IA-4, IA-5, SC-7, SC-8, SC-13, SC-28, SI-4, SI-7 |
| **PCI-DSS v4.0** | 1.1–1.3, 2.1–2.2, 3.1–3.7, 4.1–4.2, 5.1–5.3, 6.1–6.4, 7.1–7.3, 8.1–8.11, 9.1–9.11, 10.1–10.7, 11.1–11.6, 12.1–12.11 |
| **SOC 2** | CC6.1–CC6.3, CC6.6–CC6.8, CC7.1–CC7.5, CC8.1 |
| **ISO 27001:2022** | A.5.1–A.5.3, A.5.7, A.5.15, A.5.18, A.8.1–A.8.3, A.8.9, A.8.11, A.8.12, A.8.15, A.8.16, A.8.23, A.8.24, A.8.28, A.8.31, A.8.32 |

---

## References

- [Azure Policy Documentation](https://learn.microsoft.com/en-us/azure/governance/policy/)
- [Azure Policy Effects](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effects)
- [Enterprise Azure Policy as Code (EPAC)](https://techcommunity.microsoft.com/t5/core-infrastructure-and-security/azure-enterprise-policy-as-code-a-new-approach/ba-p/3607843)
- [Azure Sovereign Policy Design](https://github.com/MicrosoftDocs/azure-sovereign-clouds/blob/main/articles/public/design-sovereign-policies.md)
