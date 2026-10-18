# VPC Service Controls Module

Creates Google Cloud VPC Service Controls service perimeters with access policies, access levels, and ingress/egress policies.

## Usage

```hcl
module "vpc_sc" {
  source          = "./modules/gcp-compliance/vpc-service-controls"
  organization_id = "123456789"

  perimeter_name     = "datacenter_perimeter"
  perimeter_resources = ["projects/123456789012"]

  restricted_services = [
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "compute.googleapis.com",
  ]

  access_levels = {
    "corp_network" = {
      combining_function = "AND"
      ip_subnetworks    = ["203.0.113.0/24"]
      required_access_levels = []
      members           = []
      negate            = false
      require_screen_lock = true
      require_admin_approval = false
      os_type           = "DESKTOP_CHROME_OS"
      minimum_version   = "120.0.0"
      regions           = ["US"]
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
| create_access_policy | Create a new access policy | bool | true | no |
| existing_access_policy_id | Existing access policy ID | string | null | no |
| access_policy_title | Title for the access policy | string | "Data Center Commander..." | no |
| create_service_perimeter | Create a service perimeter | bool | true | no |
| perimeter_name | Name of the service perimeter | string | "datacenter_perimeter" | no |
| perimeter_resources | Project IDs in the perimeter | list(string) | [] | no |
| restricted_services | Services to restrict | list(string) | [bigquery, storage, compute, ...] | no |
| vpc_accessible_services_restriction | Enable VPC accessible services restriction | bool | true | no |
| vpc_accessible_services | Services accessible from within perimeter | list(string) | [bigquery, storage, ...] | no |
| ingress_from_identity_type | Identity type for ingress | string | "IDENTITY_TYPE_UNSPECIFIED" | no |
| ingress_source_resource | Ingress source resource | string | "" | no |
| ingress_to_resources | Ingress destination resources | list(string) | [] | no |
| ingress_to_service_name | Ingress destination service | string | "storage.googleapis.com" | no |
| ingress_to_method | Ingress destination method | string | "*" | no |
| egress_from_identity_type | Identity type for egress | string | "IDENTITY_TYPE_UNSPECIFIED" | no |
| egress_to_resources | Egress destination resources | list(string) | [] | no |
| egress_to_service_name | Egress destination service | string | "storage.googleapis.com" | no |
| egress_to_method | Egress destination method | string | "*" | no |
| use_explicit_dry_run_spec | Use explicit dry run spec | bool | false | no |
| access_levels | Access level configurations | map(object) | {} | no |
| ingress_policies | Ingress policy configurations | map(object) | {} | no |
| egress_policies | Egress policy configurations | map(object) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| access_policy_id | ID of the access policy |
| access_policy_name | Resource name of the access policy |
| service_perimeter_id | ID of the service perimeter |
| service_perimeter_name | Resource name of the service perimeter |
| access_level_ids | IDs of the access levels |
| ingress_policy_ids | IDs of the ingress policies |
| egress_policy_ids | IDs of the egress policies |
