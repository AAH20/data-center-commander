# Failover Automation Module

Automated disaster recovery failover including Route 53 health checks, DNS failover, Lambda-based automation, and DR Auto Scaling Groups.

## Usage

```hcl
module "failover_automation" {
  source = "./modules/disaster-recovery/failover-automation"

  name_prefix = "prod"

  health_checks = {
    primary = {
      fqdn              = "api.example.com"
      port              = 443
      type              = "HTTPS"
      resource_path     = "/health"
      failure_threshold = 3
      request_interval  = 30
    }
  }

  failover_records = {
    api = {
      zone_id           = "Z1234567890"
      name              = "api.example.com"
      type              = "A"
      ttl               = 60
      records           = ["1.2.3.4"]
      secondary_records = ["5.6.7.8"]
      health_check_key  = "primary"
    }
  }

  enable_failover_lambda = true

  failover_alarms = {
    high-latency = {
      comparison_operator = "GreaterThanThreshold"
      evaluation_periods  = 2
      metric_name         = "TargetResponseTime"
      namespace           = "AWS/ApplicationELB"
      period              = 60
      statistic           = "Average"
      threshold           = 5.0
      description         = "Failover when latency exceeds 5s"
      dimensions = {
        LoadBalancer = "app/my-alb/1234567890"
      }
    }
  }

  sns_topic_name      = "failover-notifications"
  sns_email_endpoints = ["ops@example.com"]
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| aws | ~> 5.0 |

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| name_prefix | Prefix for all resource names | `string` | - |
| health_checks | Map of Route 53 health checks | `map(object)` | `{}` |
| failover_records | Map of Route 53 failover DNS records | `map(object)` | `{}` |
| enable_failover_lambda | Enable automated failover Lambda | `bool` | `false` |
| failover_alarms | Map of CloudWatch alarms | `map(object)` | `{}` |
| enable_dr_asg | Enable DR Auto Scaling Group | `bool` | `false` |
| sns_topic_name | SNS topic name | `string` | `null` |
| tags | Tags to apply to all resources | `map(string)` | `{}` |

## Outputs

| Name | Description |
|------|-------------|
| health_check_ids | Map of Route 53 health check IDs |
| failover_record_fqdns | Map of failover record FQDNs |
| failover_lambda_arn | ARN of the failover Lambda function |
| dr_asg_name | Name of the DR Auto Scaling Group |
| sns_topic_arn | ARN of the failover SNS topic |
