# IBM Cloud VPC Module

Creates an IBM Cloud VPC with subnets, public gateways, network ACLs, security groups, and flow logs.

## Usage

```hcl
module "vpc" {
  source = "./modules/ibm/vpc"

  name       = "datacenter-vpc"
  subnets = {
    zone-1 = { zone = "us-south-1", total_ipv4_address_count = 256 }
    zone-2 = { zone = "us-south-2", total_ipv4_address_count = 256 }
  }
  public_gateways = {
    zone-1 = { zone = "us-south-1" }
    zone-2 = { zone = "us-south-2" }
  }
  tags = ["production", "data-center-commander"]
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
| name | Name prefix | string | - | yes |
| address_prefix_management | Address prefix mode (auto/manual) | string | auto | no |
| address_prefixes | Address prefixes map | map | {} | no |
| subnets | Subnets map | map | {} | no |
| public_gateways | Public gateways map | map | {} | no |
| resource_group_id | Resource group ID | string | null | no |
| classic_access | Enable classic access | bool | false | no |
| create_network_acl | Create network ACL | bool | false | no |
| network_acl_rules | Network ACL rules | list | [] | no |
| create_security_group | Create security group | bool | false | no |
| security_group_rules | Security group rules | map | {} | no |
| enable_flow_logs | Enable flow logs | bool | false | no |
| flow_log_storage_bucket | COS bucket for flow logs | string | null | no |
| tags | Resource tags | list(string) | [] | no |

## Outputs

| Name | Description |
|------|-------------|
| vpc_id | VPC ID |
| vpc_crn | VPC CRN |
| vpc_name | VPC name |
| subnet_ids | Map of subnet IDs |
| subnet_crns | Map of subnet CRNs |
| public_gateway_ids | Map of public gateway IDs |
| security_group_id | Security group ID |
| network_acl_id | Network ACL ID |
| flow_log_id | Flow log ID |
