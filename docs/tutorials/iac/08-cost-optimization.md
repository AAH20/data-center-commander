# Tutorial 08: Cost Optimization with IaC

## Overview

Cost optimization is a critical aspect of data center management. This tutorial covers how to use Infrastructure as Code to implement cost controls, optimize resource utilization, and automate cost-saving measures.

## Learning Objectives

- Understand cloud cost drivers
- Implement cost allocation and tagging strategies
- Use IaC to enforce cost controls
- Optimize compute, storage, and networking costs
- Automate cost reporting and alerting

## Cost Optimization Framework

```
┌─────────────────────────────────────────────────────────────┐
│                  Cost Optimization Lifecycle                 │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  MEASURE │→ │  ANALYZE │→ │ OPTIMIZE │→ │  GOVERN  │  │
│  │          │  │          │  │          │  │          │  │
│  │ - Tagging│  │ - Reports│  │ - Rightsizing│ - Policies│  │
│  │ - Budgets│  │ - Alerts │  │ - Spot/RI │  │ - Budgets│  │
│  │ - Usage  │  │ - Trends │  │ - Storage │  │ - Reviews│  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│       ▲                                            │      │
│       └────────────────────────────────────────────┘      │
│                      Continuous Loop                        │
└─────────────────────────────────────────────────────────────┘
```

## Tagging Strategy

```hcl
# tagging.tf
locals {
  common_tags = {
    Environment       = var.environment
    Project           = var.project_name
    Owner             = var.team_owner
    CostCenter        = var.cost_center
    DataClassification = var.data_classification
    ManagedBy         = "terraform"
    CreatedDate       = timestamp()
  }
}

# Enforce tagging with OPA/Checkov
resource "aws_resourcegroups_group" "tag_compliance" {
  name = "${var.environment}-tag-compliance"

  resource_query {
    query = jsonencode({
      ResourceTypeFilters = ["AWS::AllSupported"]
      TagFilters = [{
        Key    = "Environment"
        Values = [var.environment]
      }]
    })
  }
}
```

## Compute Optimization

### Right-Sizing with Terraform

```hcl
# compute.tf
# Use variable maps for right-sized instance types
variable "instance_profiles" {
  type = map(object({
    instance_type = string
    cpu           = number
    memory        = number
  }))
  default = {
    micro = {
      instance_type = "t3.micro"
      cpu           = 2
      memory        = 1
    }
    small = {
      instance_type = "t3.small"
      cpu           = 2
      memory        = 2
    }
    medium = {
      instance_type = "t3.medium"
      cpu           = 2
      memory        = 4
    }
    large = {
      instance_type = "t3.large"
      cpu           = 2
      memory        = 8
    }
    xlarge = {
      instance_type = "t3.xlarge"
      cpu           = 4
      memory        = 16
    }
  }
}

resource "aws_instance" "app" {
  for_each = var.app_servers

  ami           = data.aws_ami.ubuntu.id
  instance_type = var.instance_profiles[each.value.profile].instance_type

  monitoring = true

  root_block_device {
    volume_type = "gp3"
    volume_size = each.value.disk_size
    encrypted   = true
  }

  tags = merge(local.common_tags, {
    Name = each.key
  })
}
```

### Spot Instances

```hcl
# spot.tf
resource "aws_spot_instance_request" "worker" {
  count = var.worker_count

  ami           = data.aws_ami.ubuntu.id
  instance_type = "m5.large"
  spot_price    = "0.05"

  wait_for_fulfillment = true
  spot_type            = "persistent"

  vpc_security_group_ids = [aws_security_group.worker.id]
  subnet_id              = module.vpc.private_subnets[count.index % length(module.vpc.private_subnets)]

  root_block_device {
    volume_type = "gp3"
    volume_size = 50
    encrypted   = true
  }

  tags = merge(local.common_tags, {
    Name = "worker-${count.index + 1}"
    Type = "spot"
  })
}

# Spot Fleet for diversified capacity
resource "aws_spot_fleet_request" "workers" {
  iam_fleet_role                      = aws_iam_role.spot_fleet.arn
  target_capacity                     = var.target_capacity
  allocation_strategy                 = "capacityOptimized"
  instance_interruption_behaviour     = "terminate"
  terminate_instances_with_expiration = true

  dynamic "launch_specification" {
    for_each = ["m5.large", "m5a.large", "m4.large", "m6i.large"]
    content {
      instance_type          = launch_specification.value
      ami                    = data.aws_ami.ubuntu.id
      key_name               = var.key_name
      vpc_security_group_ids = [aws_security_group.worker.id]
      subnet_id            = module.vpc.private_subnets[0]

      root_block_device {
        volume_type = "gp3"
        volume_size = 50
        encrypted   = true
      }

      tags = merge(local.common_tags, {
        Name = "spot-worker"
      })
    }
  }
}
```

### Reserved Capacity

```hcl
# reservations.tf
# Savings Plans
resource "aws_savingsplans_plan" "compute" {
  savings_plan_type = "Compute"
  term              = 3  # 3-year
  payment_option    = "Partial Upfront"
  commitment       = "100.0"  # $100/hour commitment

  # Note: Savings Plans are purchased via API, not Terraform
  # This is a placeholder for documentation
}

# Reserved Instances
resource "aws_rds_reserved_instance" "main" {
  # RDS Reserved Instances
  db_instance_class   = "db.t3.medium"
  duration            = 31536000  # 1 year in seconds
  offering_type       = "Partial Upfront"
  multi_az            = false
  instance_count      = 1
}
```

## Storage Optimization

```hcl
# storage.tf
# S3 Intelligent Tiering
resource "aws_s3_bucket_intelligent_tiering_configuration" "main" {
  bucket = aws_s3_bucket.main.id
  name   = "EntireBucket"

  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = 90
  }

  tiering {
    access_tier = "DEEP_ARCHIVE_ACCESS"
    days        = 180
  }
}

# EBS Volume Optimization
resource "aws_ebs_volume" "data" {
  availability_zone = var.az
  size              = var.size_gb
  type              = "gp3"  # Better price-performance than gp2
  iops              = 3000
  throughput        = 125
  encrypted         = true
  kms_key_id        = aws_kms_key.main.arn

  tags = merge(local.common_tags, {
    Name = "${var.environment}-data"
  })
}

# EFS Lifecycle Management
resource "aws_efs_file_system" "main" {
  creation_token   = "${var.environment}-efs"
  encrypted        = true
  kms_key_id       = aws_kms_key.main.arn
  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }

  lifecycle_policy {
    transition_to_primary_storage_class = "AFTER_1_ACCESS"
  }

  tags = merge(local.common_tags, {
    Name = "${var.environment}-efs"
  })
}

# S3 Lifecycle Rules
resource "aws_s3_bucket_lifecycle_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }

    expiration {
      days = 2555  # 7 years
    }

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}
```

## Network Cost Optimization

```hcl
# network.tf
# VPC Endpoints (reduce NAT Gateway costs)
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.private_route_table_ids

  tags = merge(local.common_tags, {
    Name = "${var.environment}-s3-endpoint"
  })
}

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.private_route_table_ids

  tags = merge(local.common_tags, {
    Name = "${var.environment}-dynamodb-endpoint"
  })
}

resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${var.region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = merge(local.common_tags, {
    Name = "${var.environment}-ecr-api-endpoint"
  })
}

# CloudFront for content delivery
resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${var.environment} CDN"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"  # North America and Europe only

  origin {
    domain_name = aws_s3_bucket.static.bucket_regional_domain_name
    origin_id   = "S3-${aws_s3_bucket.static.id}"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.main.cloudfront_access_identity_path
    }
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.static.id}"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 86400
    max_ttl                = 31536000
    compress               = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.main.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = local.common_tags
}
```

## Cost Monitoring and Alerting

```hcl
# budgets.tf
resource "aws_budgets_budget" "monthly" {
  name              = "${var.environment}-monthly-budget"
  budget_type       = "COST"
  limit_amount      = var.monthly_budget
  limit_unit        = "USD"
  time_period_start = "2024-01-01_00:00"
  time_unit         = "MONTHLY"

  cost_filter {
    name = "TagKeyValue"
    values = [
      "user:Environment$${var.environment}",
    ]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = var.alert_emails
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = var.alert_emails
  }
}

# Cost anomaly detection
resource "aws_ce_anomaly_monitor" "service" {
  name              = "${var.environment}-service-monitor"
  monitor_type      = "DIMENSIONAL"
  monitor_dimension = "SERVICE"
}

resource "aws_ce_anomaly_subscription" "main" {
  name      = "${var.environment}-anomaly-subscription"
  threshold = 100  # $100 minimum anomaly
  frequency = "IMMEDIATE"

  monitor_arn_list = [aws_ce_anomaly_monitor.service.arn]

  subscriber {
    type    = "EMAIL"
    address = var.alert_email
  }
}
```

## Auto-Scaling for Cost Efficiency

```hcl
# autoscaling.tf
resource "aws_autoscaling_group" "app" {
  name                = "${var.environment}-app-asg"
  vpc_zone_identifier = module.vpc.private_subnets
  target_group_arns   = [aws_lb_target_group.app.arn]
  health_check_type   = "ELB"

  min_size         = var.min_size
  max_size         = var.max_size
  desired_capacity = var.desired_capacity

  launch_template {
    id      = aws_launch_template.app.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "${var.environment}-app"
    propagate_at_launch = true
  }

  dynamic "tag" {
    for_each = local.common_tags
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }
}

# Target tracking scaling policy
resource "aws_autoscaling_policy" "cpu" {
  name                   = "${var.environment}-cpu-target"
  autoscaling_group_name = aws_autoscaling_group.app.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value = 50.0
  }
}

# Scheduled scaling for predictable patterns
resource "aws_autoscaling_schedule" "scale_up" {
  scheduled_action_name  = "${var.environment}-scale-up"
  min_size               = 4
  max_size               = 20
  desired_capacity       = 8
  recurrence             = "0 8 * * MON-FRI"
  autoscaling_group_name = aws_autoscaling_group.app.name
}

resource "aws_autoscaling_schedule" "scale_down" {
  scheduled_action_name  = "${var.environment}-scale-down"
  min_size               = 2
  max_size               = 20
  desired_capacity       = 2
  recurrence             = "0 18 * * MON-FRI"
  autoscaling_group_name = aws_autoscaling_group.app.name
}
```

## Cost Estimation with Infracost

```yaml
# .github/workflows/cost-estimation.yml
name: Cost Estimation

on:
  pull_request:
    paths:
      - 'terraform/**'

jobs:
  infracost:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Infracost
        uses: infracost/actions/setup@v2
        with:
          api-key: ${{ secrets.INFRACOST_API_KEY }}

      - name: Generate cost estimate
        run: |
          infracost breakdown --path terraform/ \
            --format json \
            --out-file /tmp/infracost.json

      - name: Post cost comment
        uses: infracost/actions/comment@v2
        with:
          path: /tmp/infracost.json
          behavior: update
```

## Best Practices

1. **Tag everything** — Enable cost allocation and chargeback
2. **Use spot instances** — For fault-tolerant workloads, save up to 90%
3. **Right-size continuously** — Monitor utilization and adjust
4. **Leverage reserved capacity** — For predictable workloads
5. **Optimize storage tiers** — Move cold data to cheaper storage
6. **Use VPC endpoints** — Reduce NAT Gateway data transfer costs
7. **Implement auto-scaling** — Scale down during low demand
8. **Review costs weekly** — Catch anomalies early

## Next Steps

- [Tutorial 04: Policy as Code](./04-policy.md)
- [Tutorial 08: Cost Optimization](./08-cost-optimization.md)
- [Tutorial 10: Monitoring](./10-monitoring.md)

## References

- [AWS Cost Optimization](https://aws.amazon.com/architecture/cost-optimization/)
- [Infracost](https://www.infracost.io/)
- [AWS Well-Architected Cost Pillar](https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/welcome.html)
