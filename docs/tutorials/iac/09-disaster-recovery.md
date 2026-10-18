# Tutorial 09: Disaster Recovery with IaC

## Overview

Disaster Recovery (DR) ensures business continuity when infrastructure fails. This tutorial covers how to design, implement, and automate disaster recovery strategies using Infrastructure as Code.

## Learning Objectives

- Understand DR concepts (RPO, RTO)
- Design multi-region architectures
- Implement backup and restore automation
- Automate failover and failback
- Test DR procedures regularly

## DR Concepts

| Term | Definition | Example |
|------|-----------|---------|
| RPO | Recovery Point Objective — Maximum acceptable data loss | 1 hour of data |
| RTO | Recovery Time Objective — Maximum acceptable downtime | 4 hours to restore |
| RTA | Recovery Time Actual — Actual time to recover | 2.5 hours |

## DR Strategies

```
┌─────────────────────────────────────────────────────────────┐
│                    DR Strategy Spectrum                      │
│                                                             │
│  Backup & Restore ──→ Pilot Light ──→ Warm Standby ──→ Multi-Site │
│  (Low cost,         (Medium cost,   (Higher cost,    (Highest cost, │
│   high RTO)          medium RTO)     low RTO)        near-zero RTO) │
│                                                             │
│  RPO: 24h+           RPO: Hours       RPO: Minutes     RPO: Near-zero │
│  RTO: 24-48h         RTO: 4-24h       RTO: 1-4h        RTO: Minutes   │
│  Cost: $             Cost: $$         Cost: $$$        Cost: $$$$    │
└─────────────────────────────────────────────────────────────┘
```

## Multi-Region Architecture

```hcl
# multi_region.tf
# Primary region
provider "aws" {
  alias  = "primary"
  region = "us-east-1"
}

# Secondary region
provider "aws" {
  alias  = "secondary"
  region = "us-west-2"
}

# Primary VPC
module "vpc_primary" {
  providers = { aws = aws.primary }
  source    = "terraform-aws-modules/vpc/aws"
  version   = "~> 5.0"

  name = "primary-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["us-east-1a", "us-east-1b", "us-east-1c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = false

  tags = var.common_tags
}

# Secondary VPC
module "vpc_secondary" {
  providers = { aws = aws.secondary }
  source    = "terraform-aws-modules/vpc/aws"
  version   = "~> 5.0"

  name = "secondary-vpc"
  cidr = "10.1.0.0/16"

  azs             = ["us-west-2a", "us-west-2b", "us-west-2c"]
  private_subnets = ["10.1.1.0/24", "10.1.2.0/24", "10.1.3.0/24"]
  public_subnets  = ["10.1.101.0/24", "10.1.102.0/24", "10.1.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = false

  tags = var.common_tags
}
```

## Database Replication

```hcl
# database.tf
# Primary RDS instance
resource "aws_db_instance" "primary" {
  provider = aws.primary

  identifier           = "primary-db"
  engine               = "postgres"
  engine_version       = "15.4"
  instance_class       = "db.r5.large"
  allocated_storage    = 100
  max_allocated_storage = 500

  db_name  = "app"
  username = var.db_username
  password = var.db_password

  multi_az               = true
  storage_encrypted       = true
  deletion_protection     = true
  skip_final_snapshot     = false
  final_snapshot_identifier = "primary-db-final"

  backup_retention_period = 35
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = var.common_tags
}

# Cross-region read replica
resource "aws_db_instance" "secondary" {
  provider = aws.secondary

  identifier          = "secondary-db"
  replicate_source_db = aws_db_instance.primary.arn

  instance_class = "db.r5.large"

  multi_az            = false
  storage_encrypted   = true
  deletion_protection = true

  # Read replica specific
  auto_minor_version_upgrade = true

  tags = var.common_tags
}

# Global database (Aurora)
resource "aws_rds_global_cluster" "main" {
  provider = aws.primary

  global_cluster_identifier = "global-db"
  engine                    = "aurora-postgresql"
  engine_version            = "15.4"
  database_name             = "app"
  storage_encrypted         = true
}

resource "aws_rds_cluster" "primary" {
  provider = aws.primary

  cluster_identifier        = "primary-cluster"
  global_cluster_identifier = aws_rds_global_cluster.main.id
  engine                    = "aurora-postgresql"
  engine_version            = "15.4"
  database_name             = "app"
  master_username           = var.db_username
  master_password           = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.primary.name
  vpc_security_group_ids = [aws_security_group.database.id]

  backup_retention_period = 35
  preferred_backup_window = "03:00-04:00"

  enabled_cloudwatch_logs_exports = ["postgresql"]

  tags = var.common_tags
}

resource "aws_rds_cluster" "secondary" {
  provider = aws.secondary

  cluster_identifier        = "secondary-cluster"
  global_cluster_identifier = aws_rds_global_cluster.main.id
  engine                    = "aurora-postgresql"
  engine_version            = "15.4"

  db_subnet_group_name   = aws_db_subnet_group.secondary.name
  vpc_security_group_ids = [aws_security_group.database_secondary.id]

  tags = var.common_tags
}
```

## Backup Automation

```hcl
# backup.tf
resource "aws_backup_vault" "main" {
  provider = aws.primary

  name        = "${var.environment}-backup-vault"
  kms_key_arn = aws_kms_key.backup.arn

  tags = var.common_tags
}

resource "aws_backup_plan" "daily" {
  provider = aws.primary

  name = "${var.environment}-daily-backup"

  rule {
    rule_name         = "daily-backup"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 5 ? * * *)"

    lifecycle {
      delete_after = 35
    }

    copy_action {
      destination_vault_arn = aws_backup_vault.secondary.arn

      lifecycle {
        delete_after = 365
      }
    }
  }

  rule {
    rule_name         = "monthly-backup"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 5 1 * ? *)"

    lifecycle {
      cold_storage_after = 30
      delete_after       = 2555  # 7 years
    }

    copy_action {
      destination_vault_arn = aws_backup_vault.secondary.arn

      lifecycle {
        cold_storage_after = 30
        delete_after       = 2555
      }
    }
  }

  advanced_backup_setting {
    resource_type = "EC2"
    backup_options = {
      WindowsVSS = "enabled"
    }
  }
}

resource "aws_backup_selection" "main" {
  provider = aws.primary

  iam_role_arn = aws_iam_role.backup.arn
  name         = "${var.environment}-backup-selection"
  plan_id      = aws_backup_plan.daily.id

  selection_tag {
    type  = "STRINGEQUALS"
    key   = "Backup"
    value = "true"
  }

  resources = [
    aws_db_instance.primary.arn,
    aws_efs_file_system.main.arn,
  ]
}

# Cross-region backup vault
resource "aws_backup_vault" "secondary" {
  provider = aws.secondary

  name        = "${var.environment}-backup-vault-secondary"
  kms_key_arn = aws_kms_key.backup_secondary.arn

  tags = var.common_tags
}
```

## DNS Failover with Route 53

```hcl
# route53.tf
resource "aws_route53_health_check" "primary" {
  fqdn              = var.primary_domain
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 30

  regions = ["us-east-1", "us-west-1", "eu-west-1"]

  tags = merge(var.common_tags, {
    Name = "primary-health-check"
  })
}

resource "aws_route53_record" "primary" {
  zone_id = aws_route53_zone.main.zone_id
  name    = var.domain_name
  type    = "A"

  failover_routing_policy {
    type = "PRIMARY"
  }

  alias {
    name                   = aws_lb.primary.dns_name
    zone_id                = aws_lb.primary.zone_id
    evaluate_target_health = true
  }

  health_check_id = aws_route53_health_check.primary.id
  set_identifier  = "primary"
}

resource "aws_route53_record" "secondary" {
  provider = aws.secondary

  zone_id = aws_route53_zone.main.zone_id
  name    = var.domain_name
  type    = "A"

  failover_routing_policy {
    type = "SECONDARY"
  }

  alias {
    name                   = aws_lb.secondary.dns_name
    zone_id                = aws_lb.secondary.zone_id
    evaluate_target_health = true
  }

  set_identifier = "secondary"
}
```

## S3 Cross-Region Replication

```hcl
# replication.tf
# Primary bucket
resource "aws_s3_bucket" "primary" {
  provider = aws.primary

  bucket = "${var.environment}-data-primary"

  tags = var.common_tags
}

resource "aws_s3_bucket_versioning" "primary" {
  provider = aws.primary

  bucket = aws_s3_bucket.primary.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Secondary bucket
resource "aws_s3_bucket" "secondary" {
  provider = aws.secondary

  bucket = "${var.environment}-data-secondary"

  tags = var.common_tags
}

resource "aws_s3_bucket_versioning" "secondary" {
  provider = aws.secondary

  bucket = aws_s3_bucket.secondary.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Replication configuration
resource "aws_s3_bucket_replication_configuration" "main" {
  provider = aws.primary

  bucket = aws_s3_bucket.primary.id
  role   = aws_iam_role.replication.arn

  rule {
    id     = "replicate-all"
    status = "Enabled"
    priority = 1

    delete_marker_replication {
      status = "Enabled"
    }

    destination {
      bucket        = aws_s3_bucket.secondary.arn
      storage_class = "STANDARD_IA"

      replication_time {
        status  = "Enabled"
        minutes = 15
      }

      metrics {
        status  = "Enabled"
        minutes = 15
      }
    }
  }
}
```

## Automated Failover

```hcl
# failover.tf
# Lambda function for automated failover
resource "aws_lambda_function" "failover" {
  provider = aws.primary

  function_name = "${var.environment}-failover"
  role          = aws_iam_role.lambda_failover.arn
  handler       = "index.handler"
  runtime       = "python3.11"
  timeout       = 300

  filename         = data.archive_file.failover_lambda.output_path
  source_code_hash = data.archive_file.failover_lambda.output_base64sha256

  environment {
    variables = {
      PRIMARY_REGION   = "us-east-1"
      SECONDARY_REGION = "us-west-2"
      DOMAIN_NAME      = var.domain_name
      ROUTE53_ZONE_ID  = aws_route53_zone.main.zone_id
    }
  }

  tags = var.common_tags
}

# CloudWatch alarm to trigger failover
resource "aws_cloudwatch_metric_alarm" "primary_health" {
  provider = aws.primary

  alarm_name          = "${var.environment}-primary-health"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 3
  metric_name         = "HealthCheckStatus"
  namespace           = "AWS/Route53"
  period              = 60
  statistic           = "Minimum"
  threshold           = 1
  alarm_description   = "Primary region health check failed"
  alarm_actions       = [aws_sns_topic.failover.arn]

  dimensions = {
    HealthCheckId = aws_route53_health_check.primary.id
  }
}

# SNS topic for failover notifications
resource "aws_sns_topic" "failover" {
  provider = aws.primary

  name = "${var.environment}-failover"

  tags = var.common_tags
}

resource "aws_sns_topic_subscription" "email" {
  provider = aws.primary

  topic_arn = aws_sns_topic.failover.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
```

## DR Testing

```hcl
# dr_test.tf
# Route 53 recovery control
resource "aws_route53recoverycontrolsafety_rule" "dr_test" {
  name = "${var.environment}-dr-test-rule"

  asserted_control {
    arn = aws_route53recoverycontrolcluster.main.arn
  }

  rule_config {
    inverted = false
    type     = "AND"
  }

  target_control {
    arn = aws_route53recoverycontrolcluster.main.arn
  }
}

# DR testing automation
resource "aws_ssm_document" "dr_test" {
  provider = aws.primary

  name          = "${var.environment}-dr-test"
  document_type = "Automation"

  content = jsonencode({
    schemaVersion = "0.3"
    description   = "DR Test Automation"
    parameters = {
      TestType = {
        type        = "String"
        description = "Type of DR test"
        default     = "failover"
      }
    }
    mainSteps = [
      {
        name   = "runFailoverTest"
        action = "aws:runCommand"
        inputs = {
          DocumentName = "AWS-RunShellScript"
          InstanceIds  = ["{{InstanceId}}"]
          Parameters = {
            commands = [
              "#!/bin/bash",
              "echo 'Starting DR test...'",
              "aws route53 update-health-check --health-check-id {{HealthCheckId}} --disabled",
              "sleep 300",
              "echo 'DR test complete. Check secondary region.'"
            ]
          }
        }
      }
    ]
  })
}
```

## Best Practices

1. **Define RPO/RTO clearly** — Align with business requirements
2. **Automate everything** — Manual processes fail during disasters
3. **Test regularly** — DR plans that aren't tested don't work
4. **Document procedures** — Clear runbooks for on-call engineers
5. **Monitor replication** — Ensure data is actually being replicated
6. **Use infrastructure as code** — Rebuild anything, anywhere
7. **Plan for partial failures** — Not all failures are region-wide
8. **Communicate** — Keep stakeholders informed during DR events

## Next Steps

- [Tutorial 07: Security](./07-security.md)
- [Tutorial 08: Cost Optimization](./08-cost-optimization.md)
- [Tutorial 10: Monitoring](./10-monitoring.md)

## References

- [AWS Disaster Recovery](https://aws.amazon.com/disaster-recovery/)
- [AWS Well-Architected Reliability Pillar](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/welcome.html)
- [NIST SP 800-34](https://csrc.nist.gov/publications/detail/sp/800-34/rev-1/final)
