# CloudWatch Module

Creates CloudWatch log groups, metric alarms, dashboards, and event rules.

## Usage

```hcl
module "monitoring" {
  source = "./modules/aws/cloudwatch"

  log_groups = {
    "/aws/rds/datacenter-db" = {
      retention_days = 30
    }
    "/aws/ec2/app-servers" = {
      retention_days = 14
    }
  }

  metric_alarms = {
    "high-cpu" = {
      comparison_operator = "GreaterThanThreshold"
      evaluation_periods  = 2
      metric_name         = "CPUUtilization"
      namespace           = "AWS/EC2"
      period              = 300
      statistic           = "Average"
      threshold           = 80
      alarm_actions       = [aws_sns_topic.alerts.arn]
    }
  }

  tags = {
    Environment = "production"
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| log_groups | Log groups map | map(object) | {} | no |
| metric_alarms | Metric alarms map | map(object) | {} | no |
| dashboard_name | Dashboard name | string | null | no |
| dashboard_body | Dashboard JSON | string | null | no |
| event_rules | Event rules map | map(object) | {} | no |
| event_targets | Event targets map | map(object) | {} | no |
| tags | Resource tags | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| log_group_names | Log group names |
| log_group_arns | Log group ARNs |
| alarm_names | Alarm names |
| dashboard_name | Dashboard name |
