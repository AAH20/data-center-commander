output "trail_id" {
  description = "ID of the CloudTrail trail"
  value       = aws_cloudtrail.this.id
}

output "trail_arn" {
  description = "ARN of the CloudTrail trail"
  value       = aws_cloudtrail.this.arn
}

output "trail_home_region" {
  description = "Home region of the CloudTrail trail"
  value       = aws_cloudtrail.this.home_region
}

output "trail_s3_bucket_name" {
  description = "S3 bucket name used by the CloudTrail trail"
  value       = aws_cloudtrail.this.s3_bucket_name
}
