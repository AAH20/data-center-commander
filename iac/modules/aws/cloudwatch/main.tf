terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_cloudwatch_log_group" "this" {
  for_each = var.log_groups

  name              = each.key
  retention_in_days = each.value.retention_days
  kms_key_id        = each.value.kms_key_id

  tags = merge(var.tags, {
    Name = each.key
  })
}

resource "aws_cloudwatch_metric_alarm" "this" {
  for_each = var.metric_alarms

  alarm_name          = each.key
  comparison_operator = each.value.comparison_operator
  evaluation_periods  = each.value.evaluation_periods
  metric_name         = each.value.metric_name
  namespace           = each.value.namespace
  period              = each.value.period
  statistic           = each.value.statistic
  threshold           = each.value.threshold
  alarm_description   = each.value.description
  alarm_actions       = each.value.alarm_actions
  ok_actions          = each.value.ok_actions
  insufficient_data_actions = each.value.insufficient_data_actions
  dimensions          = each.value.dimensions
  treat_missing_data  = each.value.treat_missing_data

  tags = merge(var.tags, {
    Name = each.key
  })
}

resource "aws_cloudwatch_dashboard" "this" {
  count          = var.dashboard_name != null ? 1 : 0
  dashboard_name = var.dashboard_name
  dashboard_body = var.dashboard_body

  tags = var.tags
}

resource "aws_cloudwatch_event_rule" "this" {
  for_each = var.event_rules

  name                = each.key
  description         = each.value.description
  event_pattern       = each.value.event_pattern
  schedule_expression = each.value.schedule_expression
  state               = each.value.state

  tags = merge(var.tags, {
    Name = each.key
  })
}

resource "aws_cloudwatch_event_target" "this" {
  for_each = { for k, v in var.event_targets : k => v }

  rule      = each.value.rule_name
  target_id = each.value.target_id
  arn       = each.value.arn
  role_arn  = each.value.role_arn
}
