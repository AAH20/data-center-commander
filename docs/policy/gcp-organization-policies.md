# GCP Organization Policies

> **Cloud:** Google Cloud Platform (GCP)  
> **Policy Type:** Organization Policy Constraints  
> **Location:** Terraform modules (deployed via `google_org_policy_policy`)

---

## Overview

GCP Organization Policies are centralized constraints on resource configuration across the GCP resource hierarchy (Organization → Folder → Project). Unlike IAM (which controls *who can do what*), organization policies control *what is allowed at all*—even a Project Owner cannot override them.

### Key Characteristics

| Attribute | Detail |
|-----------|--------|
| **Language** | YAML (gcloud CLI) or Terraform (`google_org_policy_policy`) |
| **Scope** | Organization, Folder, Project |
| **Inheritance** | Child policies override parent by default |
| **Override prevention** | `inheritFromParent: true` |
| **Effect timing** | Immediate (no TTL) |
| **Existing resources** | Not auto-remediated |
| **Audit** | Cloud Audit Logs |
| **Custom constraints** | CEL expressions (preview) |

---

## Policy Types

| Type | Description | Example |
|------|-------------|---------|
| **Boolean Constraints** | Enforced or not (TRUE/FALSE) | `compute.disableSerialPortAccess` |
| **List Constraints** | Allow/deny specific values | `gcp.resourceLocations` (allowed regions) |
| **Custom Constraints** | CEL-based custom rules (preview) | Custom field validation |

---

## Policy YAML Syntax

### Boolean Constraint

```yaml
# Disable VM serial port access
constraint: constraints/compute.disableSerialPortAccess
booleanPolicy:
  enforced: true
```

### List Constraint

```yaml
# Restrict resource locations
constraint: constraints/gcp.resourceLocations
listPolicy:
  allowedValues:
    - in:us-locations
    - in:eu-locations
  deniedValues: []
  allValues: DENY
```

### Deny All Values

```yaml
# Deny all VM external IPs
constraint: constraints/compute.vmExternalIpAccess
listPolicy:
  allValues: DENY
```

---

## Recommended Baseline Constraints

The following constraints should be enabled at the organization level for all GCP deployments:

| Constraint | Type | Scope | Purpose |
|-----------|------|-------|---------|
| `iam.managed.disableServiceAccountKeyCreation` | Boolean | Org | Highest-impact guardrail—prevents key leaks |
| `iam.managed.disableServiceAccountKeyUpload` | Boolean | Org | Blocks externally-minted keys |
| `iam.allowedPolicyMemberDomains` | List | Org | Domain-restricted sharing |
| `compute.skipDefaultNetworkCreation` | Boolean | Org | No default VPC with permissive rules |
| `compute.requireShieldedVm` | Boolean | Org | vTPM + integrity monitoring |
| `compute.disableSerialPortAccess` | Boolean | Org | No interactive serial console |
| `compute.vmExternalIpAccess` | List | Org | Deny external IPs on VMs |
| `sql.restrictPublicIp` | Boolean | Org | No public Cloud SQL IPs |
| `storage.uniformBucketLevelAccess` | Boolean | Org | No object ACLs |
| `storage.publicAccessPrevention` | List | Org | Block public bucket access |

---

## Terraform Deployment

### Module Pattern

```hcl
variable "org_id" {
  description = "Organization ID"
  type        = string
}

variable "policies" {
  description = "Map of organization policies to apply"
  type = map(object({
    constraint      = string
    policy_type    = string
    enforce        = optional(bool)
    allowed_values = optional(list(string))
    denied_values  = optional(list(string))
  }))
}

resource "google_org_policy_policy" "this" {
  for_each = var.policies
  name     = "${var.org_id}/policies/${each.value.constraint}"
  parent   = var.org_id

  spec {
    dynamic "rules" {
      for_each = each.value.policy_type == "boolean" ? [1] : []
      content {
        enforce = each.value.enforce ? "TRUE" : "FALSE"
      }
    }

    dynamic "rules" {
      for_each = each.value.policy_type == "list" ? [1] : []
      content {
        values {
          allowed_values = length(each.value.allowed_values) > 0 ? each.value.allowed_values : null
          denied_values  = length(each.value.denied_values) > 0 ? each.value.denied_values : null
        }
      }
    }
  }
}
```

### Example Usage

```hcl
module "org_policies" {
  source = "./modules/org-policies"

  org_id = "organizations/123456789"

  policies = {
    "disable-sa-key-creation" = {
      constraint   = "constraints/iam.managed.disableServiceAccountKeyCreation"
      policy_type = "boolean"
      enforce     = true
    }
    "disable-serial-port" = {
      constraint   = "constraints/compute.disableSerialPortAccess"
      policy_type = "boolean"
      enforce     = true
    }
    "restrict-locations" = {
      constraint      = "constraints/gcp.resourceLocations"
      policy_type    = "list"
      allowed_values = ["in:us-locations", "in:eu-locations"]
    }
    "deny-vm-external-ip" = {
      constraint   = "constraints/compute.vmExternalIpAccess"
      policy_type = "list"
      denied_values = ["*"]
    }
  }
}
```

---

## gcloud CLI Deployment

### Boolean Constraint

```bash
# Disable serial port access
gcloud org-policies enable-policy \
  --organization=123456789 \
  --constraint=constraints/compute.disableSerialPortAccess
```

### List Constraint

```bash
# Restrict to US and EU locations
gcloud org-policies set-policy \
  --organization=123456789 \
  --policy-from-file=policy.yaml
```

Where `policy.yaml` contains:

```yaml
constraint: constraints/gcp.resourceLocations
listPolicy:
  allowedValues:
    - in:us-locations
    - in:eu-locations
  allValues: DENY
```

---

## Config Validator / Constraint Framework

For pre-deployment IaC validation, GCP offers:

| Tool | Purpose | Integration |
|------|---------|-------------|
| **terraform-validator** | Scans Terraform plans against policy constraints | CI/CD pipelines |
| **Constraint Framework** | OPA Gatekeeper-style CRDs for GCP resources | Kubernetes admission |
| **Custom constraints** | CEL-based rules for advanced requirements | Organization Policy API |

### terraform-validator Example

```bash
# Validate Terraform plan against org policies
terraform-validator scan \
  --policy-path=path/to/org-policies/ \
  --scan-path=path/to/terraform/
```

---

## Inheritance and Override Behavior

```
Organization (parent)
  ├── Folder A
  │     ├── Project 1 (inherits from Folder A)
  │     └── Project 2 (inherits from Folder A)
  └── Folder B
        ├── Project 3 (inherits from Folder B)
        └── Project 4 (inherits from Folder B)
```

- **Default:** Child policies override parent policies
- **Prevent override:** Set `inheritFromParent: true` on child
- **Merge behavior:** List constraints merge (union of allowed values)
- **Boolean constraints:** Child `enforced: true` cannot be overridden to `false` by parent

---

## Best Practices

### DO

- Deploy baseline constraints at the organization level
- Use Terraform for version-controlled policy management
- Test constraints in a sandbox project before org-wide deployment
- Use `inheritFromParent: true` for critical security constraints
- Monitor Cloud Audit Logs for policy violations
- Use terraform-validator in CI/CD pipelines
- Document exception processes for temporary overrides

### DON'T

- Don't rely on IAM alone—org policies provide defense-in-depth
- Don't forget that existing resources are not auto-remediated
- Don't create conflicting constraints at different hierarchy levels
- Don't use custom constraints in production without thorough testing
- Don't ignore the ~15 minute propagation delay for policy changes
- Don't forget that constraints are fixed by Google—you configure them, you don't define new ones (except custom constraints in preview)

---

## Strengths

- Native GCP integration—enforced at the API level
- Simple, readable constraint model
- Terraform-native management via `google_org_policy_policy`
- Effective even against Project Owners (cannot be overridden by IAM)
- Immediate effect (no propagation delay)
- Cloud Audit Logs integration

## Limitations

- GCP-only (no multi-cloud coverage)
- Constraints are fixed by Google—you configure them, you don't define new ones (except custom constraints in preview)
- No auto-remediation for existing resources
- No built-in compliance dashboard (use Security Command Center)
- Policy changes can take up to 15 minutes to propagate
- Limited to resource configuration constraints (not network-level or identity-level)

---

## Compliance Mapping

| Framework | Controls |
|-----------|----------|
| **CIS GCP Foundations** | 1.1–1.15, 2.1–2.15, 3.1–3.10, 4.1–4.15, 5.1–5.15, 6.1–6.147 |
| **NIST SP 800-53** | AC-2, AC-3, AC-5, AC-6, AC-16, AU-6, AU-9, CM-3, CM-5, IA-2, IA-4, IA-5, SC-7, SC-8, SC-13, SC-28, SI-4, SI-7 |
| **PCI-DSS v4.0** | 1.1–1.3, 2.1–2.2, 3.1–3.7, 4.1–4.2, 5.1–5.3, 6.1–6.4, 7.1–7.3, 8.1–8.11, 9.1–9.11, 10.1–10.7, 11.1–11.6, 12.1–12.11 |
| **SOC 2** | CC6.1–CC6.3, CC6.6–CC6.8, CC7.1–CC7.5, CC8.1 |
| **ISO 27001** | A.9.1–A.9.4, A.12.1–A.12.6, A.13.1–A.13.2, A.14.1–A.14.2, A.15.1–A.15.2, A.16.1, A.17.1–A.17.2, A.18.1–A.18.2 |

---

## References

- [GCP Organization Policy Documentation](https://cloud.google.com/resource-manager/docs/organization-policy/overview)
- [GCP Organization Policy Constraints](https://cloud.google.com/resource-manager/docs/organization-policy/org-policy-constraints)
- [GCP Organization Policies Guide](https://policyascode.dev/guides/gcp-policy-guide)
- [GCP Org Policies to Enable by Default (Terraform)](https://chmielewski.dev/tutorial/gcp-organization-policies-defaults-terraform-module)
