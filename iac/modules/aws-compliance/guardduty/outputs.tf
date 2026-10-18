output "detector_id" {
  description = "ID of the GuardDuty detector"
  value       = aws_guardduty_detector.this.id
}

output "detector_account_id" {
  description = "Account ID associated with the GuardDuty detector"
  value       = aws_guardduty_detector.this.account_id
}

output "member_ids" {
  description = "Map of member account IDs to their GuardDuty member IDs"
  value       = { for id, member in aws_guardduty_member.this : id => member.id }
}

output "publishing_destination_id" {
  description = "ID of the GuardDuty publishing destination (if created)"
  value       = var.publishing_destination_s3_arn != null ? aws_guardduty_publishing_destination.this[0].id : null
}
