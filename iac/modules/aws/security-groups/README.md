# Security Groups Module

Creates an AWS security group with configurable ingress and egress rules.

## Usage

```hcl
module "web_sg" {
  source = "./modules/aws/security-groups"

  name        = "web-sg"
  description = "Security group for web servers"
  vpc_id      = module.vpc.vpc_id

  ingress_rules = [
    {
      description = "HTTP from anywhere"
      from_port   = 80
      to_port     = 80
      ip_protocol = "tcp"
      cidr_ipv4   = "0.0.0.0/0"
    },
    {
      description = "HTTPS from anywhere"
      from_port   = 443
      to_port     = 443
      ip_protocol = "tcp"
      cidr_ipv4   = "0.0.0.0/0"
    }
  ]

  egress_rules = [
    {
      description = "Allow all outbound"
      from_port   = 0
      to_port     = 0
      ip_protocol = "-1"
      cidr_ipv4   = "0.0.0.0/0"
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
| name | Security group name | string | - | yes |
| description | Description | string | - | yes |
| vpc_id | VPC ID | string | - | yes |
| ingress_rules | Ingress rules list | list(object) | [] | no |
| egress_rules | Egress rules list | list(object) | [] | no |
| tags | Resource tags | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| security_group_id | Security group ID |
| security_group_name | Security group name |
| security_group_arn | Security group ARN |
