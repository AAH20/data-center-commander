# Subnets Module

Creates public, private, and database subnets across multiple AZs with route tables and optional NAT gateway.

## Usage

```hcl
module "subnets" {
  source = "./modules/aws/subnets"

  name                  = "datacenter"
  vpc_id                = module.vpc.vpc_id
  public_subnet_cidrs   = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs  = ["10.0.10.0/24", "10.0.20.0/24"]
  database_subnet_cidrs = ["10.0.100.0/24", "10.0.200.0/24"]
  enable_nat_gateway    = true
  tags = {
    Environment = "production"
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| name | Name prefix | string | - | yes |
| vpc_id | VPC ID | string | - | yes |
| public_subnet_cidrs | Public subnet CIDRs | list(string) | [] | no |
| private_subnet_cidrs | Private subnet CIDRs | list(string) | [] | no |
| database_subnet_cidrs | Database subnet CIDRs | list(string) | [] | no |
| availability_zones | AZ list (auto if null) | list(string) | null | no |
| internet_gateway_id | IGW ID for public RT | string | null | no |
| enable_nat_gateway | Create NAT gateway | bool | true | no |
| tags | Resource tags | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| public_subnet_ids | Public subnet IDs |
| private_subnet_ids | Private subnet IDs |
| database_subnet_ids | Database subnet IDs |
| db_subnet_group_name | DB subnet group name |
| nat_gateway_id | NAT gateway ID |
| public_route_table_id | Public route table ID |
| private_route_table_id | Private route table ID |
