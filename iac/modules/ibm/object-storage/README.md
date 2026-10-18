# IBM Cloud Object Storage Module

Creates an IBM Cloud Object Storage (COS) bucket with optional versioning, lifecycle rules, encryption, and monitoring.

## Usage

```hcl
module "object_storage" {
  source = "./modules/ibm/object-storage"

  bucket_name = "my-datacenter-backups"
  location    = "us-south"
  storage_class = "standard"
  enable_versioning = true
  tags = ["production", "backup"]
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| ibm | ~> 1.65 |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| bucket_name | Bucket name (globally unique) | string | - | yes |
| location | Bucket location | string | us-south | no |
| storage_class | Storage class | string | standard | no |
| resource_group_id | Resource group ID | string | null | no |
| encryption_key_crn | Encryption key CRN | string | null | no |
| enable_versioning | Enable versioning | bool | false | no |
| enable_activity_tracking | Enable activity tracking | bool | false | no |
| activity_tracker_crn | Activity tracker CRN | string | null | no |
| enable_metrics_monitoring | Enable metrics monitoring | bool | false | no |
| metrics_monitoring_crn | Metrics monitoring CRN | string | null | no |
| allowed_ips | Allowed IP list | list(string) | [] | no |
| lifecycle_rules | Lifecycle rules | list | null | no |
| tags | Resource tags | list(string) | [] | no |

## Outputs

| Name | Description |
|------|-------------|
| bucket_id | Bucket ID |
| bucket_crn | Bucket CRN |
| bucket_name | Bucket name |
| bucket_location | Bucket location |
| s3_endpoint | S3-compatible endpoint |
