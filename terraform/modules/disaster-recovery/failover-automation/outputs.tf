output "health_check_ids" {
  description = "Map of Route 53 health check IDs"
  value       = { for k, v in aws_route53_health_check.primary : k => v.id }
}

output "failover_record_fqdns" {
  description = "Map of failover record FQDNs"
  value       = { for k, v in aws_route53_record.primary : k => v.fqdn }
}

output "failover_lambda_arn" {
  description = "ARN of the failover Lambda function"
  value       = var.enable_failover_lambda ? aws_lambda_function.failover[0].arn : null
}

output "failover_lambda_name" {
  description = "Name of the failover Lambda function"
  value       = var.enable_failover_lambda ? aws_lambda_function.failover[0].function_name : null
}

output "dr_asg_name" {
  description = "Name of the DR Auto Scaling Group"
  value       = var.enable_dr_asg ? aws_autoscaling_group.dr[0].name : null
}

output "sns_topic_arn" {
  description = "ARN of the failover SNS topic"
  value       = var.sns_topic_name != null ? aws_sns_topic.failover[0].arn : null
}
