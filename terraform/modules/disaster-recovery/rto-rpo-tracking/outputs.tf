output "metrics_log_group_arn" {
  description = "ARN of the DR metrics CloudWatch log group"
  value       = aws_cloudwatch_log_group.dr_metrics.arn
}

output "events_log_group_arn" {
  description = "ARN of the DR events CloudWatch log group"
  value       = aws_cloudwatch_log_group.dr_events.arn
}

output "dashboard_name" {
  description = "Name of the RTO/RPO CloudWatch dashboard"
  value       = aws_cloudwatch_dashboard.rto_rpo.dashboard_name
}

output "dashboard_arn" {
  description = "ARN of the RTO/RPO CloudWatch dashboard"
  value       = aws_cloudwatch_dashboard.rto_rpo.dashboard_arn
}

output "metrics_lambda_arn" {
  description = "ARN of the DR metrics Lambda function"
  value       = var.enable_metrics_lambda ? aws_lambda_function.metrics[0].arn : null
}

output "sns_topic_arn" {
  description = "ARN of the RTO/RPO alerts SNS topic"
  value       = var.sns_topic_name != null ? aws_sns_topic.rto_rpo_alerts[0].arn : null
}

output "rto_alarm_arns" {
  description = "Map of RTO alarm ARNs"
  value       = { for k, v in aws_cloudwatch_metric_alarm.rto_breach : k => v.arn }
}

output "rpo_alarm_arns" {
  description = "Map of RPO alarm ARNs"
  value       = { for k, v in aws_cloudwatch_metric_alarm.rpo_breach : k => v.arn }
}
