output "bucket_id" {
  description = "ID of the created COS bucket"
  value       = ibm_cos_bucket.this.id
}

output "bucket_crn" {
  description = "CRN of the created COS bucket"
  value       = ibm_cos_bucket.this.crn
}

output "bucket_name" {
  description = "Name of the created COS bucket"
  value       = ibm_cos_bucket.this.bucket_name
}

output "bucket_location" {
  description = "Location of the created COS bucket"
  value       = ibm_cos_bucket.this.location
}

output "s3_endpoint" {
  description = "S3-compatible endpoint for the bucket"
  value       = "s3.${var.location}.cloud-object-storage.appdomain.cloud"
}
