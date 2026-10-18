output "config_recorder_id" {
  description = "ID of the AWS Config configuration recorder"
  value       = aws_config_configuration_recorder.this.id
}

output "config_delivery_channel_id" {
  description = "ID of the AWS Config delivery channel"
  value       = aws_config_delivery_channel.this.id
}

output "config_role_arn" {
  description = "ARN of the IAM role used by AWS Config"
  value       = aws_iam_role.config.arn
}

output "config_managed_rule_ids" {
  description = "Map of managed rule names to their IDs"
  value       = { for name, rule in aws_config_config_rule.managed : name => rule.id }
}

output "config_custom_rule_ids" {
  description = "Map of custom rule names to their IDs"
  value       = { for name, rule in aws_config_config_rule.custom : name => rule.id }
}

output "config_aggregator_arn" {
  description = "ARN of the AWS Config aggregator (if created)"
  value       = var.config_aggregator_name != null ? aws_config_configuration_aggregator.this[0].arn : null
}
