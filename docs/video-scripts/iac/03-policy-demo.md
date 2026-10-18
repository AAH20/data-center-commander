# Video Script: Data Center Commander — Policy Demo (Checkov Custom Policies)

**Target length:** 5–6 minutes  
**Audience:** DevOps engineers, security engineers, platform teams  
**Goal:** Demonstrate how Data Center Commander uses Checkov custom policies to scan Terraform code for compliance violations before deployment.

---

## Scene 1 — Why Scan IaC (0:00–0:40)

**Visual:** Screen recording of the `policies/checkov/terraform/` directory. Show the seven custom policy files: `compliance_governance.py`, `network_security.py`, `encryption.py`, `iam_access_control.py`, `compute_security.py`, `storage_security.py`, `logging_monitoring.py`, and `data_center_specific.py`.

**Narration:**
> "Rego policies evaluate resources at runtime. But the best time to catch a misconfiguration is before it's deployed. Data Center Commander includes 60+ custom Checkov policies that scan Terraform code during development and CI/CD. These policies catch security gaps, compliance violations, and operational risks while they're still cheap to fix. Let me show you what they cover."

**On-screen text:** "Checkov · 60+ custom policies · Terraform scanning"

---

## Scene 2 — Compliance & Governance (0:40–1:40)

**Visual:** Screen recording of `policies/checkov/terraform/compliance_governance.py`. Highlight the check classes: `ResourceHasTags`, `BackupVaultExists`, `BackupPlanExists`, `EnvironmentTagSeparation`, `CostAllocationTags`, `S3BucketLifecyclePolicy`, `RDSSnapshotRetention`, `VPCHasDHCPOptions`, `ResourceHasName`, `S3BucketReplicationEnabled`.

**Narration:**
> "The compliance governance policies enforce operational discipline. Every resource must have required tags: Environment, Owner, and Project. Cost allocation tags — CostCenter, Billing, or Department — are mandatory for chargebacks. Environment tags must be one of the valid values: dev, staging, prod, test, QA. AWS Backup vaults and plans must exist. S3 buckets must have lifecycle policies for cost optimization. RDS instances must retain snapshots for at least 7 days. Cross-region replication is required for disaster recovery."

**Action:** Show the `REQUIRED_TAGS` list and `VALID_ENVIRONMENTS` list in the code.

---

## Scene 3 — Network Security (1:40–2:50)

**Visual:** Screen recording of `policies/checkov/terraform/network_security.py`. Highlight the check classes: `RDPPortNotPubliclyAccessible`, `SSHPortNotPubliclyAccessible`, `DatabasePortNotPubliclyAccessible`, `VPCFlowLogsEnabled`, `NetworkACLRestricted`, `SubnetHasPrivateIP`, `VPCEndpointEnabled`, `SecurityGroupHasDescription`, `NoWildcardCIDR`, `TransitGatewayHasAutoAcceptDisabled`.

**Narration:**
> "Network security policies are strict. RDP port 3389 and SSH port 22 must not be publicly accessible — no exceptions. Database ports — 1433, 3306, 5432, 27017, 9200, 5433, 6379, 11211, 1521, 50000 — must not be open to the internet. VPC flow logs must be enabled for network monitoring. NACLs must not allow unrestricted traffic. Subnets must not auto-assign public IPs. VPC endpoints must be used for AWS services instead of public internet. Security groups must have descriptions. Wildcard CIDR `0.0.0.0/0` is prohibited for non-web ports. Transit gateways must not auto-accept shared attachments."

**Action:** Show the `DB_PORTS` list and `WEB_PORTS` list in the code.

---

## Scene 4 — Encryption & IAM (2:50–4:00)

**Visual:** Split-screen showing `encryption.py` on the left and `iam_access_control.py` on the right.

**Narration:**
> "Encryption policies cover the full key lifecycle. KMS key rotation must be enabled. KMS key policies must not use wildcard principals. ALB and ELB listeners must use HTTPS with an SSL policy. CloudFront distributions must use TLS 1.2 or higher. S3 buckets must enforce SSL/TLS only. Secrets Manager secrets must have rotation enabled. ACM certificates must be properly configured. DynamoDB tables must have encryption. ElastiCache clusters must have both at-rest and in-transit encryption.

IAM policies enforce least privilege. IAM policies must not use wildcard actions. Role trust policies must not allow wildcard principals. IAM users must have MFA. Password policies must require 14+ characters with symbols, numbers, uppercase, and lowercase. IAM roles must have descriptions. Policies must be attached to groups or roles, not directly to users. No policy may grant AdministratorAccess. Session duration must not exceed one hour. Full-access patterns — `s3:*`, `ec2:*`, `iam:*`, `rds:*` — are prohibited."

---

## Scene 5 — Compute, Storage, Monitoring & Data Center (4:00–5:15)

**Visual:** Quick-cut tour of the remaining four policy files.

**Narration:**
> "Compute security policies require IMDSv2, detailed monitoring, no public IPs, encrypted root volumes, no hardcoded credentials in user data, health checks for auto-scaling groups, security groups on launch templates, dedicated tenancy for sensitive workloads, and no burstable instance types in production.

Storage security policies require EBS encryption, encrypted snapshots, S3 default encryption, public access blocks, versioning, logging, RDS storage encryption, backup retention, no public RDS access, and S3 object lock for compliance.

Logging and monitoring policies require multi-region CloudTrail, log file validation, CloudTrail S3 bucket logging, CloudWatch log retention of 30+ days, alarm actions, GuardDuty, Security Hub, AWS Config, VPC flow logs capturing all traffic, and S3 bucket CloudTrail validation.

Data center specific policies require Multi-AZ RDS, multi-AZ auto-scaling groups, cross-zone load balancing, S3 cross-region replication, DynamoDB global tables, Route 53 health checks, CloudFront WAF, Shield Advanced, Direct Connect backup, and VPN redundant tunnels."

---

## Scene 6 — Running Checkov (5:15–5:45)

**Visual:** Terminal recording showing Checkov scanning the OpenTofu codebase.

**Narration:**
> "Checkov integrates into your CI/CD pipeline. It scans Terraform plans, Terraform code, Kubernetes manifests, and more. Failed checks block the build. Passed checks are logged for audit."

**Action — terminal command:**
```bash
checkov -d opentofu/ --framework terraform \
  --check DC_GOV_001,DC_NET_001,DC_CRYPTO_001,DC_IAM_001 \
  --compact
```

---

## Scene 7 — Close (5:45–6:00)

**Visual:** Return to the `policies/checkov/terraform/` directory. Fade to the Checkov README on GitHub.

**Narration:**
> "Sixty-plus custom Checkov policies scan every line of Terraform code before it reaches production. They cover governance, network security, encryption, IAM, compute, storage, monitoring, and data center specific requirements. The policies are open source under AGPL-3.0. Add your own, customize existing ones, and integrate them into your pipeline."

**On-screen text:** GitHub repo URL · "policies/checkov/"

---

## Production notes

- Use screen recordings from the actual `policies/checkov/terraform/` directory.
- Show actual Python check class code — don't just describe it.
- The split-screen views should be clean and readable.
- Terminal recordings should show actual Checkov output.
- Caption all narration.
