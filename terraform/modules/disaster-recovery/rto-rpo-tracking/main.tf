terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ─── CloudWatch Log Group for DR Metrics ──────────────────────────────────────

resource "aws_cloudwatch_log_group" "dr_metrics" {
  name              = "/dr/${var.name_prefix}/metrics"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_id

  tags = merge(var.tags, { Name = "${var.name_prefix}-dr-metrics" })
}

# ─── CloudWatch Log Group for DR Events ───────────────────────────────────────

resource "aws_cloudwatch_log_group" "dr_events" {
  name              = "/dr/${var.name_prefix}/events"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_id

  tags = merge(var.tags, { Name = "${var.name_prefix}-dr-events" })
}

# ─── Custom Metric Filters for RTO/RPO Tracking ───────────────────────────────

resource "aws_cloudwatch_log_metric_filter" "rto" {
  for_each = var.rto_metric_filters

  name           = each.key
  pattern        = each.value.pattern
  log_group_name = aws_cloudwatch_log_group.dr_events.name

  metric_transformation {
    name          = each.value.metric_name
    namespace     = "DR/${var.name_prefix}"
    value         = each.value.value
    default_value = "0"
    unit          = "Seconds"
  }
}

resource "aws_cloudwatch_log_metric_filter" "rpo" {
  for_each = var.rpo_metric_filters

  name           = each.key
  pattern        = each.value.pattern
  log_group_name = aws_cloudwatch_log_group.dr_events.name

  metric_transformation {
    name          = each.value.metric_name
    namespace     = "DR/${var.name_prefix}"
    value         = each.value.value
    default_value = "0"
    unit          = "Seconds"
  }
}

# ─── RTO/RPO CloudWatch Alarms ────────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "rto_breach" {
  for_each = var.rto_alarms

  alarm_name          = "${var.name_prefix}-rto-${each.key}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = each.value.evaluation_periods
  metric_name         = each.value.metric_name
  namespace           = "DR/${var.name_prefix}"
  period              = each.value.period
  statistic           = "Maximum"
  threshold           = each.value.threshold_seconds
  alarm_description   = "RTO breach: ${each.key} exceeded ${each.value.threshold_seconds}s"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions
  treat_missing_data  = "notBreaching"

  dimensions = each.value.dimensions

  tags = merge(var.tags, { Name = "${var.name_prefix}-rto-${each.key}" })
}

resource "aws_cloudwatch_metric_alarm" "rpo_breach" {
  for_each = var.rpo_alarms

  alarm_name          = "${var.name_prefix}-rpo-${each.key}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = each.value.evaluation_periods
  metric_name         = each.value.metric_name
  namespace           = "DR/${var.name_prefix}"
  period              = each.value.period
  statistic           = "Maximum"
  threshold           = each.value.threshold_seconds
  alarm_description   = "RPO breach: ${each.key} exceeded ${each.value.threshold_seconds}s"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions
  treat_missing_data  = "notBreaching"

  dimensions = each.value.dimensions

  tags = merge(var.tags, { Name = "${var.name_prefix}-rpo-${each.key}" })
}

# ─── RTO/RPO Dashboard ────────────────────────────────────────────────────────

locals {
  dashboard_widgets = [
    for service, config in var.services : {
      type   = "metric"
      x      = 0
      y      = index(keys(var.services), service) * 6
      width  = 12
      height = 6
      properties = {
        title  = "${service} - RTO"
        region = var.aws_region
        metrics = [
          ["DR/${var.name_prefix}", "RTO-${service}", { "label" = "RTO (s)", "stat" = "Maximum" }]
        ]
        period = 60
        yAxis = {
          left = {
            min = 0
            max = config.rto_target_seconds * 2
          }
        }
        annotations = {
          horizontal = [
            {
              value = config.rto_target_seconds
              label = "RTO Target"
              color = "#ff0000"
            }
          ]
        }
      }
    }
  ]

  dashboard_widgets_rpo = [
    for service, config in var.services : {
      type   = "metric"
      x      = 12
      y      = index(keys(var.services), service) * 6
      width  = 12
      height = 6
      properties = {
        title  = "${service} - RPO"
        region = var.aws_region
        metrics = [
          ["DR/${var.name_prefix}", "RPO-${service}", { "label" = "RPO (s)", "stat" = "Maximum" }]
        ]
        period = 60
        yAxis = {
          left = {
            min = 0
            max = config.rpo_target_seconds * 2
          }
        }
        annotations = {
          horizontal = [
            {
              value = config.rpo_target_seconds
              label = "RPO Target"
              color = "#ff0000"
            }
          ]
        }
      }
    }
  ]
}

resource "aws_cloudwatch_dashboard" "rto_rpo" {
  dashboard_name = "${var.name_prefix}-rto-rpo-tracking"
  dashboard_body = jsonencode({
    widgets = concat(local.dashboard_widgets, local.dashboard_widgets_rpo)
  })

  tags = merge(var.tags, { Name = "${var.name_prefix}-rto-rpo-tracking" })
}

# ─── SNS Topic for RTO/RPO Breach Notifications ───────────────────────────────

resource "aws_sns_topic" "rto_rpo_alerts" {
  count = var.sns_topic_name != null ? 1 : 0

  name              = var.sns_topic_name
  kms_master_key_id = var.sns_kms_key_id
  tags              = merge(var.tags, { Name = var.sns_topic_name })
}

resource "aws_sns_topic_subscription" "rto_rpo_email" {
  for_each = var.sns_topic_name != null ? var.sns_email_endpoints : []

  topic_arn = aws_sns_topic.rto_rpo_alerts[0].arn
  protocol  = "email"
  endpoint  = each.value
}

# ─── Lambda for Custom RTO/RPO Metric Publishing ──────────────────────────────

data "aws_iam_policy_document" "metrics_lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "metrics_lambda" {
  count = var.enable_metrics_lambda ? 1 : 0

  name               = "${var.name_prefix}-dr-metrics-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.metrics_lambda_assume.json

  tags = var.tags
}

data "aws_iam_policy_document" "metrics_lambda" {
  count = var.enable_metrics_lambda ? 1 : 0

  statement {
    actions = [
      "cloudwatch:PutMetricData",
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "metrics_lambda" {
  count = var.enable_metrics_lambda ? 1 : 0

  name   = "${var.name_prefix}-dr-metrics-lambda-policy"
  role   = aws_iam_role.metrics_lambda[0].id
  policy = data.aws_iam_policy_document.metrics_lambda[0].json
}

data "archive_file" "metrics_lambda" {
  count = var.enable_metrics_lambda ? 1 : 0

  type        = "zip"
  output_path = "${path.module}/metrics_lambda.zip"

  source {
    content  = <<-EOF
      import json
      import boto3
      import os
      from datetime import datetime

      cloudwatch = boto3.client('cloudwatch')

      def handler(event, context):
          namespace = f"DR/{os.environ['NAME_PREFIX']}"
          service = event.get('service', 'unknown')
          metric_type = event.get('metric_type', 'RTO')
          value = event.get('value', 0)
          unit = event.get('unit', 'Seconds')

          cloudwatch.put_metric_data(
              Namespace=namespace,
              MetricData=[{
                  'MetricName': f'{metric_type}-{service}',
                  'Dimensions': [
                      {'Name': 'Service', 'Value': service},
                      {'Name': 'Environment', 'Value': os.environ.get('ENVIRONMENT', 'production')},
                  ],
                  'Timestamp': datetime.utcnow(),
                  'Value': value,
                  'Unit': unit
              }]
          )

          return {'status': 'success', 'metric': f'{metric_type}-{service}', 'value': value}
    EOF
    filename = "index.py"
  }
}

resource "aws_lambda_function" "metrics" {
  count = var.enable_metrics_lambda ? 1 : 0

  function_name    = "${var.name_prefix}-dr-metrics-publisher"
  role            = aws_iam_role.metrics_lambda[0].arn
  handler         = "index.handler"
  runtime         = "python3.11"
  timeout         = 30
  filename        = data.archive_file.metrics_lambda[0].output_path
  source_code_hash = data.archive_file.metrics_lambda[0].output_base64sha256

  environment {
    variables = {
      NAME_PREFIX = var.name_prefix
      ENVIRONMENT = var.environment
    }
  }

  tags = var.tags
}

# ─── EventBridge Rule for Scheduled Metric Collection ─────────────────────────

resource "aws_cloudwatch_event_rule" "metrics_collection" {
  count = var.enable_metrics_lambda ? 1 : 0

  name                = "${var.name_prefix}-dr-metrics-collection"
  description         = "Collect RTO/RPO metrics on schedule"
  schedule_expression = var.metrics_collection_schedule

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "metrics_lambda" {
  count = var.enable_metrics_lambda ? 1 : 0

  rule      = aws_cloudwatch_event_rule.metrics_collection[0].name
  target_id = "MetricsLambda"
  arn       = aws_lambda_function.metrics[0].arn

  input = jsonencode({
    service     = "all"
    metric_type = "RTO"
    value       = 0
  })
}

resource "aws_lambda_permission" "eventbridge_metrics" {
  count = var.enable_metrics_lambda ? 1 : 0

  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.metrics[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.metrics_collection[0].arn
}
