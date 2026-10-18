# DR Testing Module

Automated disaster recovery testing including backup restore tests, failover/failback tests, chaos engineering, and scheduled test execution.

## Usage

```hcl
module "dr_testing" {
  source = "./modules/disaster-recovery/dr-testing"

  name_prefix = "prod"
  aws_region  = "us-east-1"

  enable_dr_testing_lambda = true
  lambda_timeout           = 900

  scheduled_tests = {
    weekly-backup-restore = {
      schedule  = "cron(0 2 ? * 1 *)"
      test_type = "backup_restore_test"
      service   = "database"
    }
    monthly-failover = {
      schedule  = "cron(0 0 1 * ? *)"
      test_type = "failover_test"
      service   = "api.example.com"
    }
  }

  hosted_zone_id      = "Z1234567890"
  sns_topic_name      = "dr-test-notifications"
  sns_email_endpoints = ["ops@example.com"]
}
```

## Test Types

| Test Type | Description |
|-----------|-------------|
| `backup_restore_test` | Restores from latest snapshot to temporary instance, verifies data, cleans up |
| `failover_test` | Performs DNS failover to secondary, verifies propagation |
| `failback_test` | Performs DNS failback to primary, verifies propagation |
| `chaos_test` | Stops running instances, verifies auto-recovery |

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| aws | ~> 5.0 |

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| name_prefix | Prefix for all resource names | `string` | - |
| aws_region | AWS region for dashboard | `string` | `us-east-1` |
| enable_dr_testing_lambda | Enable DR testing Lambda | `bool` | `true` |
| lambda_timeout | Lambda timeout in seconds | `number` | `900` |
| scheduled_tests | Map of scheduled DR tests | `map(object)` | `{}` |
| hosted_zone_id | Route 53 hosted zone ID | `string` | `null` |
| sns_topic_name | SNS topic name | `string` | `null` |
| tags | Tags to apply to all resources | `map(string)` | `{}` |

## Outputs

| Name | Description |
|------|-------------|
| dr_testing_lambda_arn | ARN of the DR testing Lambda function |
| dr_testing_lambda_name | Name of the DR testing Lambda function |
| dr_test_results_bucket | Name of the S3 bucket for test results |
| dr_test_results_bucket_arn | ARN of the S3 bucket for test results |
| dr_testing_dashboard_name | Name of the testing dashboard |
| sns_topic_arn | ARN of the SNS topic |
| scheduled_test_rule_arns | Map of scheduled test rule ARNs |
