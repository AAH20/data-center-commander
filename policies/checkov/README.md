# Data Center Commander — Checkov Custom Policies

Custom Checkov policies for scanning data center Infrastructure as Code (IaC) with security, compliance, and operational best practices.

## Policy Categories

| Category | Prefix | Description |
|----------|--------|-------------|
| Network Security | `DC_NET_*` | VPC isolation, security groups, NACLs, public exposure |
| Compute Security | `DC_COMPUTE_*` | EC2 hardening, instance metadata, monitoring |
| Storage Security | `DC_STORAGE_*` | EBS, S3, RDS encryption and access |
| Encryption & Key Management | `DC_CRYPTO_*` | KMS, TLS, secrets rotation |
| Logging & Monitoring | `DC_MONITOR_*` | CloudTrail, CloudWatch, GuardDuty, Config |
| IAM & Access Control | `DC_IAM_*` | Policies, MFA, password policies |
| Compliance & Governance | `DC_GOV_*` | Tagging, backup, cost allocation |
| Data Center Specific | `DC_DC_*` | Multi-AZ, DR, redundancy |

## Usage

### Run Checkov with custom policies

```bash
checkov -d /path/to/terraform --external-checks-dir policies/checkov/terraform/
```

### Run with specific policy

```bash
checkov -d /path/to/terraform --external-checks-dir policies/checkov/terraform/ --check DC_NET_001
```

### Run all data center policies

```bash
checkov -d /path/to/terraform --external-checks-dir policies/checkov/terraform/ --check DC_
```

## Policy Summary

### Network Security (DC_NET_001 – DC_NET_010)
- **DC_NET_001**: RDP port 3389 not publicly accessible
- **DC_NET_002**: SSH port 22 not publicly accessible
- **DC_NET_003**: Database ports not publicly accessible
- **DC_NET_004**: VPC flow logs enabled
- **DC_NET_005**: NACLs do not allow unrestricted traffic
- **DC_NET_006**: Subnets do not auto-assign public IPs
- **DC_NET_007**: VPC endpoints configured for AWS services
- **DC_NET_008**: Security groups have descriptions
- **DC_NET_009**: No wildcard CIDR for non-web ports
- **DC_NET_010**: Transit gateway does not auto-accept shared attachments

### Compute Security (DC_COMPUTE_001 – DC_COMPUTE_010)
- **DC_COMPUTE_001**: EC2 instances require IMDSv2
- **DC_COMPUTE_002**: EC2 detailed monitoring enabled
- **DC_COMPUTE_003**: EC2 instances do not have public IPs
- **DC_COMPUTE_004**: EC2 root EBS volumes encrypted
- **DC_COMPUTE_005**: No hardcoded credentials in user data
- **DC_COMPUTE_006**: Auto Scaling health checks enabled
- **DC_COMPUTE_007**: Auto Scaling groups tagged
- **DC_COMPUTE_008**: Launch templates specify security groups
- **DC_COMPUTE_009**: EC2 dedicated tenancy
- **DC_COMPUTE_010**: No burstable instances for production

### Storage Security (DC_STORAGE_001 – DC_STORAGE_010)
- **DC_STORAGE_001**: EBS volumes encrypted
- **DC_STORAGE_002**: EBS snapshots encrypted
- **DC_STORAGE_003**: S3 default encryption enabled
- **DC_STORAGE_004**: S3 public access blocked
- **DC_STORAGE_005**: S3 versioning enabled
- **DC_STORAGE_006**: S3 logging enabled
- **DC_STORAGE_007**: RDS storage encryption enabled
- **DC_STORAGE_008**: RDS backup retention configured
- **DC_STORAGE_009**: RDS not publicly accessible
- **DC_STORAGE_010**: S3 object lock enabled

### Encryption & Key Management (DC_CRYPTO_001 – DC_CRYPTO_010)
- **DC_CRYPTO_001**: KMS key rotation enabled
- **DC_CRYPTO_002**: KMS keys have descriptions
- **DC_CRYPTO_003**: KMS key policies no wildcard principals
- **DC_CRYPTO_004**: ALB/ELB listeners use HTTPS
- **DC_CRYPTO_005**: CloudFront TLS 1.2+
- **DC_CRYPTO_006**: S3 buckets enforce SSL/TLS
- **DC_CRYPTO_007**: Secrets Manager rotation enabled
- **DC_CRYPTO_008**: ACM certificates configured
- **DC_CRYPTO_009**: DynamoDB encryption enabled
- **DC_CRYPTO_010**: ElastiCache encryption enabled

### Logging & Monitoring (DC_MONITOR_001 – DC_MONITOR_010)
- **DC_MONITOR_001**: CloudTrail enabled in all regions
- **DC_MONITOR_002**: CloudTrail log file validation
- **DC_MONITOR_003**: CloudTrail S3 bucket logging
- **DC_MONITOR_004**: CloudWatch log retention policy
- **DC_MONITOR_005**: CloudWatch alarm actions configured
- **DC_MONITOR_006**: GuardDuty enabled
- **DC_MONITOR_007**: Security Hub enabled
- **DC_MONITOR_008**: AWS Config recorder enabled
- **DC_MONITOR_009**: VPC flow logs capture all traffic
- **DC_MONITOR_010**: S3 CloudTrail validation

### IAM & Access Control (DC_IAM_001 – DC_IAM_010)
- **DC_IAM_001**: No wildcard actions in IAM policies
- **DC_IAM_002**: No wildcard principals in trust policies
- **DC_IAM_003**: IAM users have MFA
- **DC_IAM_004**: Strong IAM password policy
- **DC_IAM_005**: IAM roles have descriptions
- **DC_IAM_006**: IAM groups have users
- **DC_IAM_007**: Policies attached to groups/roles
- **DC_IAM_008**: No AdministratorAccess policies
- **DC_IAM_009**: IAM role max session duration
- **DC_IAM_010**: No full-access service policies

### Compliance & Governance (DC_GOV_001 – DC_GOV_010)
- **DC_GOV_001**: Required tags present
- **DC_GOV_002**: AWS Backup vault exists
- **DC_GOV_003**: AWS Backup plan exists
- **DC_GOV_004**: Valid environment tags
- **DC_GOV_005**: Cost allocation tags
- **DC_GOV_006**: S3 lifecycle policies
- **DC_GOV_007**: RDS snapshot retention
- **DC_GOV_008**: VPC DHCP options
- **DC_GOV_009**: Resources have name tags
- **DC_GOV_010**: S3 cross-region replication

### Data Center Specific (DC_DC_001 – DC_DC_010)
- **DC_DC_001**: RDS Multi-AZ enabled
- **DC_DC_002**: Auto Scaling multi-AZ
- **DC_DC_003**: Cross-zone load balancing
- **DC_DC_004**: S3 cross-region replication
- **DC_DC_005**: DynamoDB global tables
- **DC_DC_006**: Route 53 health checks
- **DC_DC_007**: CloudFront WAF enabled
- **DC_DC_008**: AWS Shield Advanced
- **DC_DC_009**: Direct Connect backup
- **DC_DC_010**: VPN redundant tunnels

## Supported Resources

- **AWS**: EC2, VPC, Security Groups, NACLs, S3, RDS, KMS, IAM, CloudTrail, CloudWatch, GuardDuty, Config, ALB/ELB, CloudFront, DynamoDB, ElastiCache, Route 53, Direct Connect, VPN, Transit Gateway, Auto Scaling, Launch Templates, EBS, Secrets Manager, ACM, Backup, Shield, Security Hub
- **Azure**: NSG (partial support)
- **GCP**: Compute Firewall (partial support)

## Adding New Policies

1. Create a new Python file in `policies/checkov/terraform/`
2. Extend `BaseResourceCheck` or `BaseDataCenterCheck`
3. Implement `scan_resource_conf(self, conf)` returning `CheckResult.PASSED` or `CheckResult.FAILED`
4. Use the `DC_<CATEGORY>_###` ID format
5. Update this README with the new policy

## License

MIT
