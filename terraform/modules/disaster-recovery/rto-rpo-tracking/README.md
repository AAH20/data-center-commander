# RTO/RPO Tracking Module

CloudWatch-based tracking and alerting for Recovery Time Objective (RTO) and Recovery Point Objective (RPO) metrics.

## Usage

```hcl
module "rto_rpo_tracking" {
  source = "./modules/disaster-recovery/rto-rpo-tracking"

  name_prefix = "prod"
  aws_region  = "us-east-1"

  services = {
    web-api = {
      rto_target_seconds = 300   # 5 minutes
      rpo_target_seconds = 60    # 1 minute
    }
    database = {
      rto_target_seconds = 600   # 10 minutes
      rpo_target_seconds = 300   # 5 minutes
    }
  }

  rto_alarms = {
    web-api = {
      metric_name        = "RTO-web-api"
      evaluation_periods = 1
      period             = 60
      threshold_seconds  = 300
      dimensions = {
        Service = "web-api"
      }
    }
  }

  rpo_alarms = {
    web-api = {
      metric_name        = "RPO-web-api"
      evaluation_periods = 1
      period             = 60
      threshold_seconds  = 60
      dimensions = {
        Service = "web-api"
      }
    }
  }

  enable_metrics_lambda        = true
  metrics_collection_schedule = "rate(1 minute)"
  sns_topic_name               = "rto-rpo-alerts"
  sns_email_endpoints          = ["ops@example.com"]
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
| aws_region | AWS region for dashboard | `string` | `us-east-1` |
| services | Map of services with RTO/RPO targets | `map(object)` | `{}` |
| rto_alarms | Map of RTO breach alarms | `map(object)` | `{}` |
| rpo_alarms | Map of RPO breach alarms | `map(object)` | `{}` |
| enable_metrics_lambda | Enable Lambda for custom metrics | `bool` | `false` |
| sns_topic_name | SNS topic name for alerts | `string` | `null` |
| tags | Tags to apply to all resources | `map(string)` | `{}` |

## Outputs

| Name | Description |
|------|-------------|
| metrics_log_group_arn | ARN of the DR metrics log group |
| events_log_group_arn | ARN of the DR events log group |
| dashboard_name | Name of the RTO/RPO dashboard |
| dashboard_arn | ARN of the RTO/RPO dashboard |
| metrics_lambda_arn | ARN of the metrics Lambda function |
| sns_topic_arn | ARN of the alerts SNS topic |
| rto_alarm_arns | Map of RTO alarm ARNs |
| rpo_alarm_arns | Map of RPO alarm ARNs |
