# Security Command Center Module

Creates a Google Cloud Security Command Center (SCC) source with optional notification configs, mute rules, and custom configs.

## Usage

```hcl
module "scc" {
  source          = "./modules/gcp-compliance/security-command-center"
  organization_id = "123456789"

  enable_notification_config = true
  notification_filter        = "severity >= HIGH"

  mute_rules = {
    "mute-dev-findings" = {
      filter      = "severity = LOW AND resource.type = \"google.cloud.resourcemanager.Folder\""
      description = "Mute low-severity findings in dev folders"
    }
  }
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
| organization_id | GCP organization ID (numeric) | string | - | yes |
| source_display_name | Display name for the SCC source | string | "Data Center Commander SCC Source" | no |
| source_description | Description for the SCC source | string | "Security Command Center source..." | no |
| enable_notification_config | Enable SCC notification config to Pub/Sub | bool | true | no |
| notification_config_id | ID for the notification config | string | "scc-notification-config" | no |
| notification_description | Description for the notification config | string | "SCC findings notification..." | no |
| notification_filter | Filter expression for SCC findings | string | "severity >= HIGH" | no |
| mute_rules | Map of mute rule configurations | map(object) | {} | no |
| enable_custom_config | Enable custom SCC config | bool | false | no |
| custom_config_display_name | Display name for custom config | string | "Custom SCC Config" | no |
| custom_config_description | Description for custom config | string | "Custom SCC configuration..." | no |

## Outputs

| Name | Description |
|------|-------------|
| source_id | ID of the SCC source |
| source_name | Resource name of the SCC source |
| notification_config_id | ID of the notification config |
| pubsub_topic_id | ID of the Pub/Sub topic |
| mute_config_ids | IDs of the mute configs |
