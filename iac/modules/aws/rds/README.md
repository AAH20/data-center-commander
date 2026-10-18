# RDS Module

Creates an RDS instance with automated backups, encryption, and monitoring.

## Usage

```hcl
module "database" {
  source = "./modules/aws/rds"

  identifier          = "datacenter-db"
  name                = "datacenter"
  engine              = "postgres"
  engine_version      = "15.4"
  instance_class      = "db.t3.large"
  allocated_storage   = 100
  multi_az            = true
  subnet_ids          = module.subnets.database_subnet_ids
  vpc_security_group_ids = [module.db_sg.security_group_id]

  tags = {
    Environment = "production"
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| identifier | Instance identifier | string | - | yes |
| name | Name prefix | string | - | yes |
| engine | Database engine | string | postgres | no |
| engine_version | Engine version | string | 15.4 | no |
| instance_class | Instance class | string | db.t3.medium | no |
| allocated_storage | Storage GB | number | 20 | no |
| max_allocated_storage | Max storage GB | number | 100 | no |
| storage_type | Storage type | string | gp3 | no |
| storage_encrypted | Encrypt storage | bool | true | no |
| db_name | Database name | string | datacenter | no |
| username | Master username | string | dbadmin | no |
| password | Master password | string | null | no |
| port | Database port | number | 5432 | no |
| multi_az | Multi-AZ | bool | true | no |
| publicly_accessible | Public access | bool | false | no |
| subnet_ids | Subnet IDs | list(string) | - | yes |
| db_subnet_group_name | Existing subnet group | string | null | no |
| vpc_security_group_ids | Security group IDs | list(string) | [] | no |
| backup_retention_period | Backup days | number | 7 | no |
| backup_window | Backup window | string | 03:00-04:00 | no |
| maintenance_window | Maintenance window | string | sun:04:00-sun:05:00 | no |
| deletion_protection | Deletion protection | bool | true | no |
| skip_final_snapshot | Skip final snapshot | bool | false | no |
| performance_insights_enabled | Performance Insights | bool | true | no |
| performance_insights_retention_period | PI retention days | number | 7 | no |
| monitoring_interval | Enhanced monitoring | number | 60 | no |
| monitoring_role_arn | Monitoring role ARN | string | null | no |
| enabled_cloudwatch_logs_exports | Log exports | list(string) | ["postgresql"] | no |
| tags | Resource tags | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| db_instance_id | Instance ID |
| db_instance_arn | Instance ARN |
| db_instance_endpoint | Connection endpoint |
| db_instance_address | Connection address |
| db_instance_port | Connection port |
| db_instance_name | Database name |
| db_subnet_group_name | Subnet group name |
| master_password | Master password (sensitive) |
