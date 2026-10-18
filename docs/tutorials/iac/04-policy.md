# Tutorial 04: Policy as Code

## Overview

Policy as Code (PaC) extends IaC by encoding organizational rules, governance requirements, and operational constraints into machine-readable policies. This tutorial covers how to define, enforce, and manage policies that govern your data center infrastructure.

## Learning Objectives

- Understand the policy as code paradigm
- Write policies in Rego (OPA) and Sentinel
- Implement policy enforcement in CI/CD pipelines
- Create custom policy libraries
- Manage policy exceptions and exemptions

## Policy as Code vs Compliance as Code

| Aspect | Policy as Code | Compliance as Code |
|--------|---------------|-------------------|
| Scope | Organizational rules | Regulatory requirements |
| Source | Internal teams | External standards |
| Examples | Naming conventions, instance types | Encryption, access controls |
| Flexibility | Highly customizable | Fixed by regulation |
| Enforcement | Preventive + detective | Primarily preventive |

## Policy Framework Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Policy Engine                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │    OPA      │  │  Sentinel   │  │    Checkov      │ │
│  │   (Rego)    │  │  (HCL)      │  │   (Python)      │ │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘ │
│         │                │                   │          │
│         └────────────────┼───────────────────┘          │
│                          │                              │
│                   ┌──────▼──────┐                       │
│                   │  Policy     │                       │
│                   │  Decision   │                       │
│                   │  Point      │                       │
│                   └──────┬──────┘                       │
│                          │                              │
│              ┌───────────┼───────────┐                  │
│              │           │           │                  │
│         ┌────▼───┐ ┌────▼───┐ ┌────▼───┐              │
│         │ ALLOW  │ │ DENY   │ │ WARN   │              │
│         └────────┘ └────────┘ └────────┘              │
└─────────────────────────────────────────────────────────┘
```

## Writing OPA Policies

### Basic Policy Structure

```rego
# policies/lib/common.rego
package common

import future.keywords.if
import future.keywords.in

# Helper: check if resource has required labels
has_required_labels(resource, required) if {
    missing := required - object.keys(resource.labels)
    count(missing) == 0
}

# Helper: check if resource is in allowed region
in_allowed_region(resource, allowed_regions) if {
    resource.region in allowed_regions
}

# Helper: check resource naming convention
matches_naming_convention(name, pattern) if {
    regex.match(pattern, name)
}
```

### Resource Policies

```rego
# policies/compute.rego
package compute

import future.keywords.if
import future.keywords.in
import data.common

# Deny instances outside approved regions
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_instance"
    not common.in_allowed_region(resource.change.after, var.allowed_regions)
    msg := sprintf("Instance '%s' is in unapproved region '%s'. Allowed: %s", 
        [resource.address, resource.change.after.region, var.allowed_regions])
}

# Deny non-approved instance families
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_instance"
    not startswith(resource.change.after.instance_type, var.allowed_instance_families[_])
    msg := sprintf("Instance type '%s' is not in approved families", 
        [resource.change.after.instance_type])
}

# Require detailed monitoring
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_instance"
    not resource.change.after.monitoring
    msg := sprintf("Instance '%s' must have detailed monitoring enabled", [resource.address])
}

# Deny public IP assignment
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_instance"
    resource.change.after.associate_public_ip_address == true
    msg := sprintf("Instance '%s' must not have a public IP address", [resource.address])
}
```

### Network Policies

```rego
# policies/network.rego
package network

import future.keywords.if
import future.keywords.in

# Deny overly permissive security groups
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_security_group"
    rule := resource.change.after.ingress[_]
    rule.cidr_blocks[_] == "0.0.0.0/0"
    msg := sprintf("Security group '%s' has overly permissive ingress rule", [resource.address])
}

# Require specific tags on network resources
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type in ["aws_vpc", "aws_subnet", "aws_route_table"]
    not resource.change.after.tags
    msg := sprintf("Network resource '%s' must have tags", [resource.address])
}

# Deny default VPC usage
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_instance"
    resource.change.after.subnet_id == "subnet-default"
    msg := sprintf("Instance '%s' must not use the default subnet", [resource.address])
}
```

### Cost Control Policies

```rego
# policies/cost.rego
package cost

import future.keywords.if
import future.keywords.in

# Deny expensive instance types in non-production
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_instance"
    var.environment != "production"
    startswith(resource.change.after.instance_type, "p4")  # GPU instances
    msg := sprintf("GPU instances not allowed in %s environment", [var.environment])
}

# Require cost allocation tags
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type != "aws_default_vpc"
    not resource.change.after.tags.CostCenter
    msg := sprintf("Resource '%s' must have a CostCenter tag", [resource.address])
}

# Deny unattached EBS volumes
warn[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_ebs_volume"
    not resource.change.after.attachment
    msg := sprintf("EBS volume '%s' has no attachments", [resource.address])
}
```

## Sentinel Policies (Terraform Cloud)

```hcl
# policies/restrict-regions.sentinel
import "tfplan"

allowed_regions = [
  "us-east-1",
  "us-west-2",
  "eu-west-1",
]

all_resources = filter tfplan.resource_changes as _, rc {
  rc.mode is "managed" and
  rc.change.actions[_] is not "delete" and
  rc.change.after.region is not null
}

violations = rule {
  all_resources as _, resource {
    resource.change.after.region in allowed_regions
  }
}

main = rule {
  violations
}
```

```hcl
# policies/enforce-tagging.sentinel
import "tfplan"

required_tags = [
  "Environment",
  "Owner",
  "CostCenter",
  "DataClassification",
]

all_resources = filter tfplan.resource_changes as _, rc {
  rc.mode is "managed" and
  rc.change.actions[_] is not "delete" and
  rc.change.after.tags is not null
}

violations = rule {
  all_resources as _, resource {
    all required_tags as tag {
      resource.change.after.tags[tag] is not null
    }
  }
}

main = rule {
  violations
}
```

## Policy Enforcement in CI/CD

```yaml
# .github/workflows/policy-check.yml
name: Policy as Code

on:
  pull_request:
    paths:
      - 'terraform/**'

jobs:
  policy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3

      - name: Terraform Init
        run: terraform init -backend=false

      - name: Terraform Plan
        run: terraform plan -out=tfplan

      - name: Convert to JSON
        run: terraform show -json tfplan > tfplan.json

      - name: OPA Policy Check
        id: opa
        run: |
          RESULT=$(docker run --rm -v $(pwd):/data openpolicyagent/opa:latest \
            eval --data /data/policies/ --input /data/tfplan.json \
            "data" --format raw 2>&1)
          echo "result=$RESULT" >> $GITHUB_OUTPUT
          echo "$RESULT"

      - name: Check for Violations
        if: steps.opa.outputs.result != '[]'
        run: |
          echo "Policy violations found!"
          echo "${{ steps.opa.outputs.result }}"
          exit 1

      - name: Comment PR
        uses: actions/github-script@v7
        with:
          script: |
            const result = `${{ steps.opa.outputs.result }}`;
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## Policy Check Results\n\`\`\`json\n${result}\n\`\`\``
            });
```

## Policy Exceptions

```hcl
# policies/exceptions.hcl
exception {
  id          = "EXC-001"
  policy      = "restrict-instance-types"
  resource    = "aws_instance.gpu_training"
  reason      = "ML training workload requires GPU"
  approved_by = "platform-team"
  expires     = "2025-12-31"
  conditions = {
    environment = "staging"
    max_count   = 2
  }
}
```

```rego
# policies/exceptions.rego
package exceptions

import future.keywords.if
import future.keywords.in

# Check if exception is valid
valid_exception(exception) if {
    time.now_ns() < time.parse_rfc3339_ns(exception.expires)
}

# Get active exceptions for a resource
active_exceptions[exception] if {
    exception := data.exceptions[_]
    valid_exception(exception)
    exception.resource == input.resource_address
}
```

## Policy Testing

```python
# tests/test_policies.py
import subprocess
import json
import pytest

def run_opa(policy_path, input_file):
    """Run OPA evaluation and return results."""
    result = subprocess.run(
        ["opa", "eval", "--data", policy_path, "--input", input_file,
         "data", "--format", "json"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

def test_no_unencrypted_volumes():
    """Test that unencrypted EBS volumes are denied."""
    result = run_opa("policies/", "tests/fixtures/unencrypted_volume.json")
    assert len(result["result"][0]["expressions"][0]["value"]) > 0

def test_encrypted_volume_allowed():
    """Test that encrypted EBS volumes are allowed."""
    result = run_opa("policies/", "tests/fixtures/encrypted_volume.json")
    assert len(result["result"][0]["expressions"][0]["value"]) == 0

def test_public_ssh_denied():
    """Test that public SSH access is denied."""
    result = run_opa("policies/", "tests/fixtures/public_ssh.json")
    assert len(result["result"][0]["expressions"][0]["value"]) > 0
```

## Best Practices

1. **Start with deny policies** — Block the most critical issues first
2. **Use warn policies** for non-blocking guidance
3. **Version your policies** alongside infrastructure code
4. **Test policies** with unit tests before deploying
5. **Document exceptions** with clear justification and expiry
6. **Review policies regularly** as requirements evolve
7. **Use policy libraries** — Don't reinvent the wheel
8. **Monitor policy violations** in production, not just CI/CD

## Next Steps

- [Tutorial 03: Compliance as Code](./03-compliance.md)
- [Tutorial 07: Security](./07-security.md)
- [Tutorial 10: Monitoring](./10-monitoring.md)

## References

- [Open Policy Agent](https://www.openpolicyagent.org/)
- [Hashicorp Sentinel](https://www.hashicorp.com/sentinel)
- [AWS SCP Examples](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps_examples.html)
