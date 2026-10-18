output "dr_testing_lambda_arn" {
  description = "ARN of the DR testing Lambda function"
  value       = var.enable_dr_testing_lambda ? aws_lambda_function.dr_testing[0].arn : null
}

output "dr_testing_lambda_name" {
  description = "Name of the DR testing Lambda function"
  value       = var.enable_dr_testing_lambda ? aws_lambda_function.dr_testing[0].function_name : null
}

output "dr_test_results_bucket" {
  description = "Name of the S3 bucket for DR test results"
  value       = aws_s3_bucket.dr_test_results.id
}

output "dr_test_results_bucket_arn" {
  description = "ARN of the S3 bucket for DR test results"
  value       = aws_s3_bucket.dr_test_results.arn
}

output "dr_testing_dashboard_name" {
  description = "Name of the DR testing CloudWatch dashboard"
  value       = aws_cloudwatch_dashboard.dr_testing.dashboard_name
}

output "sns_topic_arn" {
  description = "ARN of the DR testing SNS topic"
  value       = var.sns_topic_name != null ? aws_sns_topic.dr_testing[0].arn : null
}

output "scheduled_test_rule_arns" {
  description = "Map of scheduled test EventBridge rule ARNs"
  value       = { for k, v in aws_cloudwatch_event_rule.dr_test_schedule : k => v.arn }
}
