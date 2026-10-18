output "security_hub_arn" {
  description = "ARN of the Security Hub"
  value       = var.enable_security_hub ? aws_securityhub_account.this[0].arn : null
}

output "standards_subscription_ids" {
  description = "Map of standard names to their subscription IDs"
  value       = { for name, std in aws_securityhub_standards_subscription.this : name => std.id }
}

output "member_ids" {
  description = "Map of member account IDs to their Security Hub member IDs"
  value       = { for id, member in aws_securityhub_member.this : id => member.id }
}

output "action_target_arn" {
  description = "ARN of the Security Hub action target"
  value       = var.enable_security_hub ? aws_securityhub_action_target.this[0].arn : null
}
