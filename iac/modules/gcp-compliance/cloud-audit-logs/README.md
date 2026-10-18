# Cloud Audit Logs Module

Configures Google Cloud Audit Logs with optional log sinks, custom log buckets, and log views.

## Usage

```hcl
module "audit_logs" {
  source    = "./modules/gcp-compliance/cloud-audit-logs"
  target_type = "project"
  target_id   = "my-project-id"

  enable_log_sink     = true
  sink_destination    = "bigquery.googleapis.com/projects/my-project/datasets/audit_logs"
  sink_filter         = "logName:\"logs/cloudaudit.googleapis.com\""
  sink_include_children = true
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| google | ~> 5.0 |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| target_type | Target resource type (project/folder/organization) | string | - | yes |
| target_id | Target resource ID | string | - | yes |
| exempted_members | Service accounts to exempt from audit logging | list(string) | [] | no |
| enable_log_sink | Enable log sink | bool | true | no |
| sink_name | Name of the log sink | string | "audit-log-sink" | no |
| sink_destination | Destination for the log sink | string | "" | no |
| sink_filter | Filter expression for the log sink | string | "logName:\"logs/cloudaudit.googleapis.com\"" | no |
| sink_include_children | Include child resources | bool | true | no |
| sink_exclusions | Log exclusion objects | list(object) | [] | no |
| enable_log_bucket | Enable custom log bucket | bool | false | no |
| log_bucket_location | Location for the log bucket | string | "global" | no |
| log_bucket_id | ID for the log bucket | string | "_Default" | no |
| log_bucket_description | Description for the log bucket | string | "Custom audit log bucket" | no |
| log_bucket_retention_days | Retention period in days | number | 365 | no |
| log_views | Log view configurations | map(object) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| audit_config_id | ID of the audit config resource |
| sink_id | ID of the log sink |
| sink_writer_identity | Writer identity of the log sink |
| log_bucket_id | ID of the custom log bucket |
| log_view_ids | IDs of the log views |
