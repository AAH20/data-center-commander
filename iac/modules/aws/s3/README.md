# S3 Module

Creates an S3 bucket with versioning, encryption, public access blocking, and lifecycle rules.

## Usage

```hcl
module "data_bucket" {
  source = "./modules/aws/s3"

  bucket_name = "datacenter-data-bucket"
  versioning_enabled = true

  lifecycle_rules = [
    {
      id      = "archive-old-data"
      enabled = true
      transitions = [
        { days = 90,  storage_class = "STANDARD_IA" },
        { days = 365, storage_class = "GLACIER" }
      ]
      expiration_days = 2555
    }
  ]

  tags = {
    Environment = "production"
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| bucket_name | Bucket name | string | - | yes |
| versioning_enabled | Enable versioning | bool | true | no |
| kms_key_id | KMS key for encryption | string | null | no |
| bucket_key_enabled | S3 Bucket Key | bool | true | no |
| lifecycle_rules | Lifecycle rules | list(object) | [] | no |
| bucket_policy | Bucket policy JSON | string | null | no |
| access_logging_bucket | Access log target | string | null | no |
| access_logging_prefix | Access log prefix | string | access-logs/ | no |
| tags | Resource tags | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| bucket_id | Bucket ID |
| bucket_arn | Bucket ARN |
| bucket_domain_name | Bucket domain name |
| bucket_regional_domain_name | Regional domain name |
