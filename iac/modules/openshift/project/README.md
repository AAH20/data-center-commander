# OpenShift Project Module

Creates an OpenShift Project (namespace) with optional resource quotas, limit ranges, and network policies.

## Usage

```hcl
module "dcc_project" {
  source = "./modules/openshift/project"

  name        = "data-center-commander"
  description = "Data Center Commander application project"
  part_of     = "data-center-commander"

  enable_quota = true
  quota_hard_limits = {
    cpu    = "8"
    memory = "16Gi"
    pods   = "40"
  }

  enable_limit_range          = true
  enable_network_isolation    = true
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| name | Project name | string | - | yes |
| display_name | Display name in console | string | "" | no |
| description | Project description | string | "" | no |
| part_of | app.kubernetes.io/part-of label | string | data-center-commander | no |
| labels | Additional labels | map(string) | {} | no |
| annotations | Additional annotations | map(string) | {} | no |
| enable_quota | Enable resource quota | bool | false | no |
| quota_hard_limits | Hard resource limits | map(string) | {cpu:4,memory:8Gi,pods:20} | no |
| enable_limit_range | Enable limit range | bool | false | no |
| limit_range | Limit range config | list(object) | [...] | no |
| enable_network_isolation | Enable NetworkPolicy | bool | false | no |

## Outputs

| Name | Description |
|------|-------------|
| project_name | Project name |
| project_id | Project UID |
| quota_name | Quota name (if enabled) |
| limit_range_name | Limit range name (if enabled) |
