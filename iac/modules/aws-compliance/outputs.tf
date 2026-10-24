# =============================================================================
# AWS Compliance — Outputs
# =============================================================================
# Re-exports the identifiers of the compliance services composed by this module.
# =============================================================================

output "config_recorder_id" {
  description = "ID of the AWS Config configuration recorder"
  value       = module.aws_config.config_recorder_id
}

output "guardduty_detector_id" {
  description = "ID of the GuardDuty detector"
  value       = module.guardduty.detector_id
}

output "security_hub_arn" {
  description = "ARN of the Security Hub account resource"
  value       = module.security_hub.security_hub_arn
}

output "cloudtrail_arn" {
  description = "ARN of the CloudTrail trail"
  value       = module.cloudtrail.trail_arn
}

output "access_analyzer_arn" {
  description = "ARN of the IAM Access Analyzer"
  value       = module.iam_access_analyzer.analyzer_arn
}
