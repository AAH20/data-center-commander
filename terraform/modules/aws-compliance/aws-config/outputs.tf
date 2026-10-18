output "config_recorder_id" {
  description = "ID of the AWS Config configuration recorder"
  value       = aws_config_configuration_recorder.this.id
}

output "config_delivery_channel_id" {
  description = "ID of the AWS Config delivery channel"
  value       = aws_config_delivery_channel.this.id
}

output "config_role_arn" {
  description = "ARN of the IAM role for AWS Config"
  value       = aws_iam_role.config.arn
}

output "config_managed_rules" {
  description = "List of AWS Config managed rules"
  value       = [for rule in aws_config_config_rule.managed : rule.id]
}

output "config_custom_rules" {
  description = "List of AWS Config custom rules"
  value       = [for rule in aws_config_config_rule.custom : rule.id]
}

output "config_aggregator_arn" {
  description = "ARN of the AWS Config aggregator"
  value       = var.config_aggregator_name != null ? aws_config_configuration_aggregator.this[0].arn : null
}
