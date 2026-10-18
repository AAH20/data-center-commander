# IBM Cloud IAM Module

Creates an IBM Cloud IAM access group with members, policies, and dynamic rules.

## Usage

```hcl
module "iam" {
  source = "./modules/ibm/iam"

  name        = "datacenter-admins"
  description = "Administrators for data center infrastructure"
  member_ibm_ids = ["user1@company.com", "user2@company.com"]
  policies = {
    vpc-admin = {
      roles = ["Administrator", "Manager"]
      resources = {
        attributes = {
          service = "is"
        }
      }
    }
  }
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
| name | Access group name | string | - | yes |
| description | Description | string | "" | no |
| member_ibm_ids | Member IAM IDs | list(string) | [] | no |
| policies | Policies map | map | {} | no |
| dynamic_rules | Dynamic rules map | map | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| access_group_id | Access group ID |
| access_group_name | Access group name |
| access_group_crn | Access group CRN |
| policy_ids | Map of policy IDs |
| dynamic_rule_ids | Map of dynamic rule IDs |
