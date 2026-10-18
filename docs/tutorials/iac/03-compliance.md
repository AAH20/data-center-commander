# Tutorial 03: Compliance as Code

## Overview

Compliance as Code (CaC) embeds regulatory and organizational compliance requirements directly into your infrastructure definitions. This tutorial covers how to automate compliance checks, enforce standards, and generate audit-ready evidence using IaC.

## Learning Objectives

- Understand compliance frameworks (SOC 2, PCI DSS, HIPAA, ISO 27001)
- Implement compliance checks in Terraform
- Use Open Policy Agent (OPA) for policy enforcement
- Automate compliance reporting
- Integrate compliance into CI/CD pipelines

## Compliance Frameworks

| Framework | Focus | Key Requirements |
|-----------|-------|-----------------|
| SOC 2 | Service organizations | Security, availability, confidentiality |
| PCI DSS | Payment card data | Network security, access control, encryption |
| HIPAA | Healthcare data | PHI protection, access controls, audit trails |
| ISO 27001 | Information security | Risk management, security controls |
| GDPR | EU personal data | Data protection, consent, right to erasure |
| NIST 800-53 | US Federal | Security and privacy controls |

## Compliance as Code Architecture

```
┌─────────────────────────────────────────────────────┐
│                  CI/CD Pipeline                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  Plan    │→ │  Policy  │→ │  Apply           │  │
│  │          │  │  Check   │  │  (if compliant)  │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
│                      │                              │
│                      ▼                              │
│              ┌──────────────┐                       │
│              │  OPA / Rego  │                       │
│              │  Policies    │                       │
│              └──────────────┘                       │
└─────────────────────────────────────────────────────┘
```

## Open Policy Agent (OPA) Integration

### Installation

```bash
# Install OPA
brew install opa

# Verify
opa version
```

### Writing Rego Policies

```rego
# policies/terraform/encryption.rego
package terraform.encryption

import future.keywords.if
import future.keywords.in

# Deny unencrypted EBS volumes
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_ebs_volume"
    not resource.change.after.encrypted
    msg := sprintf("EBS volume '%s' must be encrypted", [resource.address])
}

# Deny unencrypted S3 buckets
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_s3_bucket"
    not resource.change.after.server_side_encryption_configuration
    msg := sprintf("S3 bucket '%s' must have encryption enabled", [resource.address])
}

# Deny public S3 buckets
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_s3_bucket_public_access_block"
    not resource.change.after.block_public_acls
    msg := sprintf("S3 bucket '%s' must block public access", [resource.address])
}
```

```rego
# policies/terraform/networking.rego
package terraform.networking

import future.keywords.if
import future.keywords.in

# Deny security groups allowing 0.0.0.0/0 on port 22
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_security_group"
    rule := resource.change.after.ingress[_]
    rule.cidr_blocks[_] == "0.0.0.0/0"
    rule.from_port <= 22
    rule.to_port >= 22
    msg := sprintf("Security group '%s' must not allow SSH from 0.0.0.0/0", [resource.address])
}

# Deny security groups allowing 0.0.0.0/0 on port 3389
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_security_group"
    rule := resource.change.after.ingress[_]
    rule.cidr_blocks[_] == "0.0.0.0/0"
    rule.from_port <= 3389
    rule.to_port >= 3389
    msg := sprintf("Security group '%s' must not allow RDP from 0.0.0.0/0", [resource.address])
}

# Require VPC flow logs
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_vpc"
    not resource.change.after.enable_dns_hostnames
    msg := sprintf("VPC '%s' must have DNS hostnames enabled", [resource.address])
}
```

```rego
# policies/terraform/tagging.rego
package terraform.tagging

import future.keywords.if
import future.keywords.in

required_tags := {"Environment", "Owner", "CostCenter", "DataClassification"}

# Deny resources missing required tags
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type != "aws_default_vpc"
    missing := required_tags - object.keys(resource.change.after.tags)
    count(missing) > 0
    msg := sprintf("Resource '%s' is missing required tags: %s", [resource.address, concat(", ", missing)])
}
```

### Running Policy Checks

```bash
# Generate Terraform plan in JSON format
terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json

# Evaluate policies
opa eval --data policies/ --input tfplan.json "data.terraform.deny"

# Or use Conftest for Terraform-specific testing
conftest test tfplan.json
```

## Sentinel Policies (Terraform Cloud/Enterprise)

```hcl
# policies/restrict-instance-types.sentinel
import "tfplan"

# Allowed instance types
allowed_types = [
  "t3.micro", "t3.small", "t3.medium",
  "t3.large", "t3.xlarge", "t3.2xlarge",
  "m5.large", "m5.xlarge", "m5.2xlarge",
]

# Get all EC2 instances
all_instances = filter tfplan.resource_changes as _, rc {
  rc.type is "aws_instance" and
  rc.mode is "managed" and
  rc.change.actions[_] is not "delete"
}

# Validate instance types
violations = rule {
  all_instances as _, instance {
    instance.change.after.instance_type in allowed_types
  }
}

main = rule {
  violations
}
```

## Compliance Automation Pipeline

```yaml
# .github/workflows/compliance.yml
name: Compliance Check

on:
  pull_request:
    paths:
      - 'terraform/**'

jobs:
  compliance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3

      - name: Terraform Init
        run: terraform init -backend=false

      - name: Terraform Plan
        run: terraform plan -out=tfplan

      - name: Convert Plan to JSON
        run: terraform show -json tfplan > tfplan.json

      - name: Run OPA Policy Checks
        run: |
          docker run --rm -v $(pwd):/data openpolicyagent/opa:latest \
            eval --data /data/policies/ --input /data/tfplan.json \
            "data.terraform.deny" --format pretty

      - name: Run Conftest
        run: |
          docker run --rm -v $(pwd):/data openpolicyagent/conftest:latest \
            test /data/tfplan.json

      - name: Checkov Scan
        uses: bridgecrewio/checkov-action@master
        with:
          directory: terraform/
          framework: terraform
          output_format: sarif

      - name: Upload Compliance Report
        uses: actions/upload-artifact@v4
        with:
          name: compliance-report
          path: compliance-report.json
```

## Compliance Reporting

```hcl
# Generate compliance evidence
resource "local_file" "compliance_report" {
  content = jsonencode({
    timestamp    = timestamp()
    environment  = var.environment
    checks_run   = var.compliance_checks
    violations   = var.violations
    compliant    = length(var.violations) == 0
    evidence_hash = md5(jsonencode(var.resource_inventory))
  })
  filename = "${path.module}/compliance-report-${formatdate("YYYYMMDD-hhmmss", timestamp())}.json"
}
```

## Common Compliance Patterns

### Encryption Everywhere

```hcl
# Enforce encryption at rest
resource "aws_ebs_volume" "encrypted" {
  availability_zone = var.az
  size              = var.size_gb
  encrypted         = true
  kms_key_id        = aws_kms_key.ebs.arn

  tags = {
    Name        = var.name
    Encryption  = "required"
    Compliance  = "SOC2,PCI-DSS"
  }
}

# Enforce encryption in transit
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.main.arn
}
```

### Access Control

```hcl
# Enforce least privilege IAM
resource "aws_iam_role" "app" {
  name = "${var.environment}-app-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "app" {
  name = "${var.environment}-app-policy"
  role = aws_iam_role.app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.app.arn}/*"
      }
    ]
  })
}
```

### Audit Logging

```hcl
# Enable CloudTrail
resource "aws_cloudtrail" "main" {
  name                          = "${var.environment}-trail"
  s3_bucket_name                = aws_s3_bucket.logs.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_logging                = true
  kms_key_id                    = aws_kms_key.cloudtrail.arn

  event_selector {
    read_write_type           = "All"
    include_management_events = true

    data_resource {
      type   = "AWS::S3::Object"
      values = ["arn:aws:s3:::"]
    }
  }
}

# Enable VPC Flow Logs
resource "aws_flow_log" "main" {
  vpc_id          = aws_vpc.main.id
  traffic_type    = "ALL"
  iam_role_arn    = aws_iam_role.flow_logs.arn
  log_destination = aws_cloudwatch_log_group.flow_logs.arn

  tags = {
    Name = "${var.environment}-flow-logs"
  }
}
```

## Next Steps

- [Tutorial 04: Policy as Code](./04-policy.md)
- [Tutorial 07: Security](./07-security.md)
- [Tutorial 10: Monitoring](./10-monitoring.md)

## References

- [Open Policy Agent](https://www.openpolicyagent.org/)
- [Hashicorp Sentinel](https://www.hashicorp.com/sentinel)
- [Checkov](https://www.checkov.io/)
- [NIST Compliance](https://www.nist.gov/cyberframework)
