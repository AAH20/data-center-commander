# VPC Module

Creates an AWS VPC with optional flow logs to CloudWatch.

## Usage

```hcl
module "vpc" {
  source = "./modules/aws/vpc"

  name       = "datacenter-vpc"
  cidr_block = "10.0.0.0/16"
  tags = {
    Environment = "production"
    Project     = "data-center-commander"
  }
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| aws | ~> 5.0 |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| name | Name prefix | string | - | yes |
| cidr_block | VPC CIDR block | string | - | yes |
| enable_dns_support | Enable DNS support | bool | true | no |
| enable_dns_hostnames | Enable DNS hostnames | bool | true | no |
| enable_flow_logs | Enable flow logs | bool | true | no |
| flow_log_traffic_type | Traffic type (ACCEPT/REJECT/ALL) | string | ALL | no |
| flow_log_retention_days | Flow log retention | number | 30 | no |
| flow_log_iam_role_arn | IAM role ARN for flow logs | string | null | no |
| tags | Resource tags | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| vpc_id | VPC ID |
| vpc_cidr_block | VPC CIDR block |
| default_security_group_id | Default security group ID |
| flow_log_id | Flow log ID |
