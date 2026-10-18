# Backup Policies Module

AWS Backup policies for disaster recovery including backup vaults, plans, cross-region copy, and notifications.

## Usage

```hcl
module "backup_policies" {
  source = "./modules/disaster-recovery/backup-policies"

  vault_name = "production-backup-vault"
  plan_name  = "production-backup-plan"

  backup_rules = [
    {
      rule_name          = "daily-backup"
      schedule           = "cron(0 5 ? * * *)"
      cold_storage_after = 30
      delete_after       = 365
    },
    {
      rule_name          = "weekly-backup"
      schedule           = "cron(0 5 ? * 1 *)"
      cold_storage_after = 90
      delete_after       = 2555  # 7 years
    }
  ]

  backup_selections = {
    production = {
      iam_role_arn = aws_iam_role.backup.arn
      selection_tags = [
        { type = "STRINGEQUALS", key = "Environment", value = "production" }
      ]
    }
  }

  cross_region_backup_enabled  = true
  cross_region_backup_vault_arn = aws_backup_vault.secondary.arn
  sns_topic_name                = "backup-notifications"
  sns_email_endpoints           = ["ops@example.com"]
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| aws | ~> 5.0 |

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| vault_name | Name of the AWS Backup vault | `string` | - |
| plan_name | Name of the backup plan | `string` | - |
| kms_key_id | KMS key ARN for encryption | `string` | `null` |
| enable_vault_lock | Enable compliance mode vault lock | `bool` | `false` |
| backup_rules | List of backup plan rules | `list(object)` | `[]` |
| backup_selections | Map of backup selections | `map(object)` | `{}` |
| cross_region_backup_enabled | Enable cross-region backup copy | `bool` | `false` |
| sns_topic_name | SNS topic name for notifications | `string` | `null` |
| tags | Tags to apply to all resources | `map(string)` | `{}` |

## Outputs

| Name | Description |
|------|-------------|
| vault_arn | ARN of the backup vault |
| plan_id | ID of the backup plan |
| plan_arn | ARN of the backup plan |
| cross_region_plan_id | ID of the cross-region backup plan |
| sns_topic_arn | ARN of the backup notifications SNS topic |
