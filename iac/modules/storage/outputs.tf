output "aws_bucket_name" {
  description = "AWS S3 bucket name"
  value       = var.enable_aws ? aws_s3_bucket.this[0].bucket : null
}

output "aws_bucket_arn" {
  description = "AWS S3 bucket ARN"
  value       = var.enable_aws ? aws_s3_bucket.this[0].arn : null
}

output "gcp_bucket_name" {
  description = "GCP bucket name"
  value       = var.enable_gcp ? google_storage_bucket.this[0].name : null
}

output "gcp_bucket_url" {
  description = "GCP bucket URL"
  value       = var.enable_gcp ? google_storage_bucket.this[0].url : null
}

output "azure_storage_account_name" {
  description = "Azure storage account name"
  value       = var.enable_azure ? azurerm_storage_account.this[0].name : null
}

output "azure_container_name" {
  description = "Azure storage container name"
  value       = var.enable_azure ? azurerm_storage_container.this[0].name : null
}

output "azure_primary_blob_endpoint" {
  description = "Azure primary blob endpoint"
  value       = var.enable_azure ? azurerm_storage_account.this[0].primary_blob_endpoint : null
}
