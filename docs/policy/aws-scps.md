# AWS Service Control Policies (SCPs)

> **Cloud:** AWS  
> **Policy Type:** Service Control Policies (SCPs) & Resource Control Policies (RCPs)  
> **Location:** `policies/aws-scp/`

---

## Overview

AWS Service Control Policies (SCPs) are ceiling policies that define the maximum permissions available to IAM users and roles within AWS Organizations member accounts. They restrict but never grant permissions, and they are evaluated as part of AWS's IAM policy evaluation logic.

Resource Control Policies (RCPs), launched November 2024, extend this model to the resource side—defining the maximum permissions available for resources in member accounts.

### Key Characteristics

| Attribute | SCPs | RCPs |
|-----------|------|------|
| **Scope** | Principals (users, roles, root) | Resources |
| **Launched** | 2017 | November 2024 |
| **Max document size** | 10,240 characters | 5,120 characters |
| **Max direct attachments** | 10 per entity | 5 per entity (4 usable + 1 managed) |
| **Org-wide count** | 10,000 | 1,000 |
| **Management account** | Not affected | Not affected |
| **Service-linked roles** | Not affected | Not affected |
| **Grants permissions?** | No (ceiling only) | No (ceiling only) |
| **Evaluation order** | After RCPs | Before SCPs |

---

## Evaluation Order in AWS

AWS evaluates policies in the following order when determining whether an action is allowed:

1. **Explicit deny** check across all policy types (SCPs, RCPs, resource-based, identity-based, permission boundaries, session policies)
2. **RCPs** evaluated (if no Allow found → Deny)
3. **SCPs** evaluated (if no Allow found → Deny)
4. **Resource-based** policies
5. **Identity-based** policies
6. **IAM permission boundaries**
7. **Session policies**

---

## Policy Syntax

SCPs and RCPs use standard AWS IAM policy JSON syntax:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "StatementIdentifier",
      "Effect": "Deny",
      "Action": ["service:Action"],
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "aws:RequestedRegion": ["us-east-1", "us-west-2"]
        }
      }
    }
  ]
}
```

---

## Data Center Commander SCP Policies

### 24-deny-iam-policy-modifications.json

**Purpose:** Prevents unauthorized modification of IAM policies, roles, and trust relationships.

**Statements:**

| Sid | Effect | Actions | Resource |
|-----|--------|---------|----------|
| `DenyIamPolicyModification` | Deny | `iam:CreatePolicyVersion`, `iam:DeletePolicy`, `iam:DeletePolicyVersion`, `iam:SetDefaultPolicyVersion`, `iam:AttachGroupPolicy`, `iam:AttachRolePolicy`, `iam:AttachUserPolicy`, `iam:DetachGroupPolicy`, `iam:DetachRolePolicy`, `iam:DetachUserPolicy`, `iam:PutGroupPolicy`, `iam:PutRolePolicy`, `iam:PutUserPolicy`, `iam:DeleteGroupPolicy`, `iam:DeleteRolePolicy`, `iam:DeleteUserPolicy` | `*` |
| `DenyIamRoleModification` | Deny | `iam:CreateRole`, `iam:DeleteRole`, `iam:UpdateRole`, `iam:UpdateAssumeRolePolicy`, `iam:DeleteRolePermissionsBoundary`, `iam:PutRolePermissionsBoundary` | `*` |

**Use Case:** Deploy at the organization root level to prevent any account from modifying IAM configurations. This is a critical guardrail for preventing privilege escalation and unauthorized access.

**Deployment:**
```bash
aws organizations create-policy \
  --content file://policies/aws-scp/24-deny-iam-policy-modifications.json \
  --name "DenyIamPolicyModifications" \
  --type SERVICE_CONTROL_POLICY \
  --description "Prevents modification of IAM policies and roles across the organization"
```

---

### 25-deny-s3-bucket-policy.json

**Purpose:** Prevents modification of S3 bucket policies and ACLs, ensuring data access controls cannot be weakened.

**Statements:**

| Sid | Effect | Actions | Resource |
|-----|--------|---------|----------|
| `DenyS3BucketPolicyModification` | Deny | `s3:PutBucketPolicy`, `s3:DeleteBucketPolicy`, `s3:PutBucketAcl`, `s3:DeleteBucketAcl` | `*` |

**Use Case:** Deploy at the organization root level to prevent any account from modifying S3 bucket policies or ACLs. This prevents accidental or malicious exposure of S3 data.

**Deployment:**
```bash
aws organizations create-policy \
  --content file://policies/aws-scp/25-deny-s3-bucket-policy.json \
  --name "DenyS3BucketPolicyModification" \
  --type SERVICE_CONTROL_POLICY \
  --description "Prevents modification of S3 bucket policies and ACLs"
```

---

## Data Perimeter Design

SCPs and RCPs are the primary building blocks of an AWS **data perimeter**—controls ensuring access happens only between trusted identities, trusted resources, and expected networks.

| Control Objective | Primary Policy | Key Condition Keys |
|-------------------|---------------|-------------------|
| Only trusted identities can access my resources | RCP | `aws:PrincipalOrgID`, `aws:SourceOrgID`, `aws:PrincipalIsAWSService` |
| My identities can access only trusted resources | SCP | `aws:ResourceOrgID` |
| Access only from expected networks | SCP / RCP / VPC endpoint | `aws:SourceIp`, `aws:SourceVpc`, `aws:ViaAWSService` |

### Example: Organization-Wide Data Perimeter

```json
{
  "Sid": "EnforceOrgResources",
  "Effect": "Deny",
  "Action": "*",
  "Resource": "*",
  "Condition": {
    "StringNotEqualsIfExists": {
      "aws:ResourceOrgID": "o-EXAMPLE"
    }
  }
}
```

```json
{
  "Sid": "EnforceOrgIdentities",
  "Effect": "Deny",
  "Principal": "*",
  "Action": ["s3:*", "sqs:*", "kms:*"],
  "Resource": "*",
  "Condition": {
    "StringNotEqualsIfExists": {
      "aws:PrincipalOrgID": "o-EXAMPLE"
    },
    "BoolIfExists": {
      "aws:PrincipalIsAWSService": "false"
    }
  }
}
```

---

## Managing SCPs as Code

### Recommended Pattern

1. **Central Git repository** stores all SCPs and a mapping file defining attachments
2. **Pull request workflow** for all changes (review, approve, merge)
3. **CI/CD pipeline** (GitHub Actions, AWS CodePipeline) validates and deploys
4. **Two-layer separation:**
   - **Structural SCPs** at OU level: stable corporate controls (security, compliance)
   - **Account-level SCPs:** workload-specific baselines and temporary exceptions
5. **Event-driven notifications** via EventBridge + Lambda for policy changes

### Terraform Deployment

```hcl
resource "aws_organizations_policy" "deny_iam_modifications" {
  name    = "DenyIamPolicyModifications"
  type    = "SERVICE_CONTROL_POLICY"
  content = file("${path.module}/policies/aws-scp/24-deny-iam-policy-modifications.json")
}

resource "aws_organizations_policy_attachment" "deny_iam_modifications" {
  policy_id = aws_organizations_policy.deny_iam_modifications.id
  target_id = "ou-1234-56789012"  # Attach to OU
}
```

---

## Best Practices

### DO

- ✅ Deploy SCPs at the OU level, not individual accounts
- ✅ Use explicit `Deny` statements with specific actions
- ✅ Include `Condition` blocks for region and network restrictions
- ✅ Test SCPs in a sandbox account before production deployment
- ✅ Use AWS Access Analyzer to validate SCP effectiveness
- ✅ Version control all SCPs in Git
- ✅ Implement CI/CD pipelines for SCP deployment

### DON'T

- ❌ Don't attach SCPs directly to the management account (they don't apply)
- ❌ Don't use wildcard `Action: "*"` without conditions
- ❌ Don't exceed document size limits (10KB SCP, 5KB RCP)
- ❌ Don't forget that SCPs don't restrict service-linked roles
- ❌ Don't create overlapping SCPs that conflict
- ❌ Don't deploy without testing in a non-production account

---

## Strengths

- Native AWS integration—no external infrastructure required
- Preventive enforcement (deny before action executes)
- Overrides IAM permissions, even for admin users
- Mature tooling: AWS Control Tower, Access Analyzer, Security Hub integration
- RCPs close the resource-side gap that SCPs cannot address

## Limitations

- AWS-only (no multi-cloud coverage)
- SCPs do not restrict the management account or service-linked roles
- Document size limits (10KB SCP, 5KB RCP) constrain complex policies
- No built-in remediation—detection only
- Allow-list strategy is operationally demanding at scale
- RCPs are relatively new (Nov 2024) with a smaller ecosystem

---

## Compliance Mapping

| Framework | Controls |
|-----------|----------|
| **CIS AWS Foundations** | 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4 |
| **NIST SP 800-53** | AC-2, AC-3, AC-5, AC-6, AC-16, AU-6, AU-9, CM-3, CM-5, IA-2, IA-4, IA-5, SC-7, SC-8, SC-13, SC-28, SI-4, SI-7 |
| **PCI-DSS v4.0** | 1.1, 1.2, 1.3, 2.1, 2.2, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.1, 4.2, 5.1, 5.2, 5.3, 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10, 8.11, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9, 9.10, 9.11, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9, 12.10, 12.11 |
| **SOC 2** | CC6.1, CC6.2, CC6.3, CC6.6, CC6.7, CC6.8, CC7.1, CC7.2, CC7.3, CC7.4, CC7.5, CC8.1 |
| **ISO 27001** | A.9.1, A.9.2, A.9.3, A.9.4, A.12.1, A.12.2, A.12.3, A.12.4, A.12.5, A.12.6, A.13.1, A.13.2, A.14.1, A.14.2, A.15.1, A.15.2, A.16.1, A.17.1, A.17.2, A.18.1, A.18.2 |

---

## References

- [AWS Organizations SCP Documentation](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_scps.html)
- [AWS RCP Documentation](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_rcps.html)
- [How Moeve scales AWS governance with automated SCPs](https://aws.amazon.com/blogs/mt/how-moeve-scales-aws-governance-with-automated-aws-organization-service-control-policies)
- [Codify your best practices using SCPs](https://aws.amazon.com/blogs/mt/codify-your-best-practices-using-service-control-policies-part-1)
- [Manage AWS Organizations policies as code (AWS Prescriptive Guidance)](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/manage-organizations-policies-as-code.html)
