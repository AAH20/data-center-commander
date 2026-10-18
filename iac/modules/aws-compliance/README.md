# AWS Compliance-as-Code

Terraform modules for AWS compliance services: AWS Config, GuardDuty, Security Hub, CloudTrail, and IAM Access Analyzer.

## Modules

| Module | Description |
|--------|-------------|
| [aws-config](./aws-config) | AWS Config recorder, delivery channel, managed & custom rules, and aggregator |
| [guardduty](./guardduty) | GuardDuty detector with data sources, member invitations, and publishing destination |
| [security-hub](./security-hub) | Security Hub with standards, member invitations, and product integrations |
| [cloudtrail](./cloudtrail) | CloudTrail with multi-region support, log validation, event selectors, and insights |
| [iam-access-analyzer](./iam-access-analyzer) | IAM Access Analyzer with unused access analysis and archive rules |

## Usage

```hcl
module "aws_compliance" {
  source = "./modules/aws-compliance"

  aws_region           = "us-east-1"
  environment          = "production"
  compliance_s3_bucket = "my-compliance-logs-bucket"
  compliance_kms_key_id = "arn:aws:kms:us-east-1:123456789012:key/abcd1234-..."
}
```

## Prerequisites

- Terraform >= 1.0
- AWS Provider >= 5.0
- An S3 bucket for compliance logs (CloudTrail + AWS Config)
- (Optional) A KMS key for log encryption

## Deployment

```bash
cd iac/modules/aws-compliance
terraform init
terraform plan
terraform apply
```

## Compliance Coverage

### AWS Config Rules (Managed)
- S3 bucket public read/write prohibited
- RDS storage encryption
- EC2 volume in-use check
- IAM password policy
- Root account MFA
- IAM user no policies check
- Security group open to world

### GuardDuty
- S3 log analysis
- Kubernetes audit log analysis
- EC2 malware protection
- Configurable finding publishing frequency

### Security Hub Standards
- AWS Foundational Security Best Practices
- CIS AWS Foundations Benchmark
- PCI DSS

### CloudTrail
- Multi-region trail
- Log file validation
- Data resource event selectors (S3, Lambda)
- Call rate and error rate insights

### IAM Access Analyzer
- Account-level analyzer
- Unused access analysis (90-day threshold)
- Archive rules support
