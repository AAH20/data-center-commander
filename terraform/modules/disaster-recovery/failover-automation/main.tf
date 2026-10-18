terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ─── Route 53 Health Checks ───────────────────────────────────────────────────

resource "aws_route53_health_check" "primary" {
  for_each = var.health_checks

  fqdn              = each.value.fqdn
  port              = each.value.port
  type              = each.value.type
  resource_path     = each.value.resource_path
  failure_threshold = each.value.failure_threshold
  request_interval  = each.value.request_interval

  regions = each.value.regions

  tags = merge(var.tags, {
    Name = each.key
  })
}

# ─── Route 53 Failover Records ────────────────────────────────────────────────

resource "aws_route53_record" "primary" {
  for_each = var.failover_records

  zone_id = each.value.zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = each.value.ttl

  failover_routing_policy {
    type = "PRIMARY"
  }

  health_check_id = aws_route53_health_check.primary[each.value.health_check_key].id
  set_identifier  = "${each.key}-primary"

  records = each.value.records
}

resource "aws_route53_record" "secondary" {
  for_each = var.failover_records

  zone_id = each.value.zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = each.value.ttl

  failover_routing_policy {
    type = "SECONDARY"
  }

  set_identifier = "${each.key}-secondary"

  records = each.value.secondary_records
}

# ─── Failover Lambda Function ─────────────────────────────────────────────────

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "failover_lambda" {
  count = var.enable_failover_lambda ? 1 : 0

  name               = "${var.name_prefix}-failover-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json

  tags = var.tags
}

data "aws_iam_policy_document" "failover_lambda" {
  count = var.enable_failover_lambda ? 1 : 0

  statement {
    actions = [
      "route53:ChangeResourceRecordSets",
      "route53:ListResourceRecordSets",
      "route53:GetHostedZone",
      "autoscaling:DescribeAutoScalingGroups",
      "autoscaling:UpdateAutoScalingGroup",
      "autoscaling:SetDesiredCapacity",
      "ec2:DescribeInstances",
      "rds:DescribeDBInstances",
      "rds:PromoteReadReplica",
      "sns:Publish",
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "failover_lambda" {
  count = var.enable_failover_lambda ? 1 : 0

  name   = "${var.name_prefix}-failover-lambda-policy"
  role   = aws_iam_role.failover_lambda[0].id
  policy = data.aws_iam_policy_document.failover_lambda[0].json
}

data "archive_file" "failover_lambda" {
  count = var.enable_failover_lambda ? 1 : 0

  type        = "zip"
  output_path = "${path.module}/failover_lambda.zip"

  source {
    content  = <<-EOF
      import json
      import boto3
      import os

      route53 = boto3.client('route53')
      autoscaling = boto3.client('autoscaling')
      sns = boto3.client('sns')

      def handler(event, context):
          action = event.get('action', 'failover')
          hosted_zone_id = os.environ['HOSTED_ZONE_ID']
          record_name = os.environ['RECORD_NAME']
          record_type = os.environ.get('RECORD_TYPE', 'A')
          secondary_records = json.loads(os.environ['SECONDARY_RECORDS'])
          primary_records = json.loads(os.environ['PRIMARY_RECORDS'])
          sns_topic = os.environ.get('SNS_TOPIC_ARN')

          if action == 'failover':
              new_records = secondary_records
              msg = 'FAILOVER: Switched DNS to secondary'
          elif action == 'failback':
              new_records = primary_records
              msg = 'FAILBACK: Switched DNS to primary'
          else:
              raise ValueError(f'Unknown action: {action}')

          route53.change_resource_record_sets(
              HostedZoneId=hosted_zone_id,
              ChangeBatch={
                  'Changes': [{
                      'Action': 'UPSERT',
                      'ResourceRecordSet': {
                          'Name': record_name,
                          'Type': record_type,
                          'TTL': 60,
                          'ResourceRecords': [{'Value': r} for r in new_records],
                          'SetIdentifier': 'primary' if action == 'failback' else 'secondary',
                          'Failover': 'PRIMARY' if action == 'failback' else 'SECONDARY'
                      }
                  }]
              }
          )

          if sns_topic:
              sns.publish(TopicArn=sns_topic, Subject=f'DR {action.upper()} executed', Message=msg)

          return {'status': 'success', 'action': action, 'message': msg}
    EOF
    filename = "index.py"
  }
}

resource "aws_lambda_function" "failover" {
  count = var.enable_failover_lambda ? 1 : 0

  function_name    = "${var.name_prefix}-failover-handler"
  role            = aws_iam_role.failover_lambda[0].arn
  handler         = "index.handler"
  runtime         = "python3.11"
  timeout         = 60
  filename        = data.archive_file.failover_lambda[0].output_path
  source_code_hash = data.archive_file.failover_lambda[0].output_base64sha256

  environment {
    variables = {
      HOSTED_ZONE_ID    = var.failover_records[keys(var.failover_records)[0]].zone_id
      RECORD_NAME       = var.failover_records[keys(var.failover_records)[0]].name
      RECORD_TYPE       = var.failover_records[keys(var.failover_records)[0]].type
      PRIMARY_RECORDS   = jsonencode(var.failover_records[keys(var.failover_records)[0]].records)
      SECONDARY_RECORDS = jsonencode(var.failover_records[keys(var.failover_records)[0]].secondary_records)
      SNS_TOPIC_ARN     = var.sns_topic_arn
    }
  }

  tags = var.tags
}

# ─── CloudWatch Alarms for Failover Triggers ──────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "failover_trigger" {
  for_each = var.failover_alarms

  alarm_name          = each.key
  comparison_operator = each.value.comparison_operator
  evaluation_periods  = each.value.evaluation_periods
  metric_name         = each.value.metric_name
  namespace           = each.value.namespace
  period              = each.value.period
  statistic           = each.value.statistic
  threshold           = each.value.threshold
  alarm_description   = each.value.description
  alarm_actions       = var.enable_failover_lambda ? [aws_lambda_function.failover[0].arn] : []
  ok_actions          = []

  dimensions = each.value.dimensions

  tags = merge(var.tags, { Name = each.key })
}

# ─── EventBridge Rule for Automated Failover ──────────────────────────────────

resource "aws_cloudwatch_event_rule" "failover" {
  count = var.enable_failover_lambda ? 1 : 0

  name        = "${var.name_prefix}-failover-rule"
  description = "Trigger failover on health check failure"

  event_pattern = jsonencode({
    source      = ["aws.route53"]
    detail-type = ["Route 53 Health Check Status Change"]
    detail = {
      Status = ["Unhealthy"]
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "failover_lambda" {
  count = var.enable_failover_lambda ? 1 : 0

  rule      = aws_cloudwatch_event_rule.failover[0].name
  target_id = "FailoverLambda"
  arn       = aws_lambda_function.failover[0].arn
}

resource "aws_lambda_permission" "eventbridge" {
  count = var.enable_failover_lambda ? 1 : 0

  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.failover[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.failover[0].arn
}

# ─── Auto Scaling Group for DR Region ─────────────────────────────────────────

resource "aws_autoscaling_group" "dr" {
  count = var.enable_dr_asg ? 1 : 0

  name                = "${var.name_prefix}-dr-asg"
  vpc_zone_identifier = var.dr_subnet_ids
  target_group_arns   = var.dr_target_group_arns
  health_check_type   = "ELB"
  min_size            = var.dr_min_size
  max_size            = var.dr_max_size
  desired_capacity    = var.dr_desired_capacity

  launch_template {
    id      = var.dr_launch_template_id
    version = "$Latest"
  }

  dynamic "tag" {
    for_each = merge(var.tags, { Name = "${var.name_prefix}-dr-asg" })
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }
}

# ─── SNS Topic for Failover Notifications ─────────────────────────────────────

resource "aws_sns_topic" "failover" {
  count = var.sns_topic_name != null ? 1 : 0

  name              = var.sns_topic_name
  kms_master_key_id = var.sns_kms_key_id
  tags              = merge(var.tags, { Name = var.sns_topic_name })
}

resource "aws_sns_topic_subscription" "failover_email" {
  for_each = var.sns_topic_name != null ? var.sns_email_endpoints : []

  topic_arn = aws_sns_topic.failover[0].arn
  protocol  = "email"
  endpoint  = each.value
}
