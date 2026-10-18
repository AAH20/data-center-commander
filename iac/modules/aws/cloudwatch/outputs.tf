output "log_group_names" {
  description = "Names of created log groups"
  value       = [for k, v in aws_cloudwatch_log_group.this : v.name]
}

output "log_group_arns" {
  description = "ARNs of created log groups"
  value       = [for k, v in aws_cloudwatch_log_group.this : v.arn]
}

output "alarm_names" {
  description = "Names of created alarms"
  value       = [for k, v in aws_cloudwatch_metric_alarm.this : v.alarm_name]
}

output "dashboard_name" {
  description = "Dashboard name"
  value       = var.dashboard_name != null ? aws_cloudwatch_dashboard.this[0].dashboard_name : null
}
