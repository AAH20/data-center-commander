output "vault_arn" {
  description = "ARN of the backup vault"
  value       = aws_backup_vault.this.arn
}

output "vault_name" {
  description = "Name of the backup vault"
  value       = aws_backup_vault.this.name
}

output "plan_id" {
  description = "ID of the backup plan"
  value       = aws_backup_plan.this.id
}

output "plan_arn" {
  description = "ARN of the backup plan"
  value       = aws_backup_plan.this.arn
}

output "cross_region_plan_id" {
  description = "ID of the cross-region backup plan"
  value       = var.cross_region_backup_enabled ? aws_backup_plan.cross_region[0].id : null
}

output "sns_topic_arn" {
  description = "ARN of the backup notifications SNS topic"
  value       = var.sns_topic_name != null ? aws_sns_topic.backup_notifications[0].arn : null
}
