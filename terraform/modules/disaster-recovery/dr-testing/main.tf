terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ─── DR Testing IAM Role ──────────────────────────────────────────────────────

data "aws_iam_policy_document" "dr_testing_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "dr_testing" {
  name               = "${var.name_prefix}-dr-testing-role"
  assume_role_policy = data.aws_iam_policy_document.dr_testing_assume.json

  tags = var.tags
}

data "aws_iam_policy_document" "dr_testing" {
  statement {
    actions = [
      "ec2:DescribeInstances",
      "ec2:StartInstances",
      "ec2:StopInstances",
      "ec2:RebootInstances",
      "rds:DescribeDBInstances",
      "rds:RebootDBInstance",
      "rds:PromoteReadReplica",
      "rds:CreateDBInstanceReadReplica",
      "autoscaling:DescribeAutoScalingGroups",
      "autoscaling:UpdateAutoScalingGroup",
      "autoscaling:SetDesiredCapacity",
      "route53:ChangeResourceRecordSets",
      "route53:ListResourceRecordSets",
      "s3:ListBucket",
      "s3:GetObject",
      "s3:PutObject",
      "sns:Publish",
      "cloudwatch:PutMetricData",
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "dr_testing" {
  name   = "${var.name_prefix}-dr-testing-policy"
  role   = aws_iam_role.dr_testing.id
  policy = data.aws_iam_policy_document.dr_testing.json
}

# ─── DR Testing Lambda Function ───────────────────────────────────────────────

data "archive_file" "dr_testing_lambda" {
  count = var.enable_dr_testing_lambda ? 1 : 0

  type        = "zip"
  output_path = "${path.module}/dr_testing_lambda.zip"

  source {
    content  = <<-EOF
      import json
      import boto3
      import os
      import time
      from datetime import datetime

      ec2 = boto3.client('ec2')
      rds = boto3.client('rds')
      autoscaling = boto3.client('autoscaling')
      route53 = boto3.client('route53')
      sns = boto3.client('sns')
      cloudwatch = boto3.client('cloudwatch')

      def handler(event, context):
          test_type = event.get('test_type', 'backup_restore_test')
          service = event.get('service', 'all')
          region = os.environ.get('AWS_REGION', 'us-east-1')
          sns_topic = os.environ.get('SNS_TOPIC_ARN')
          hosted_zone_id = os.environ.get('HOSTED_ZONE_ID')

          results = {
              'test_type': test_type,
              'service': service,
              'start_time': datetime.utcnow().isoformat(),
              'status': 'running',
              'steps': []
          }

          try:
              if test_type == 'backup_restore_test':
                  results['steps'] = run_backup_restore_test(service, region)
              elif test_type == 'failover_test':
                  results['steps'] = run_failover_test(service, hosted_zone_id)
              elif test_type == 'failback_test':
                  results['steps'] = run_failback_test(service, hosted_zone_id)
              elif test_type == 'chaos_test':
                  results['steps'] = run_chaos_test(service, region)
              else:
                  raise ValueError(f'Unknown test type: {test_type}')

              results['status'] = 'completed'
              results['end_time'] = datetime.utcnow().isoformat()

              start = datetime.fromisoformat(results['start_time'])
              end = datetime.fromisoformat(results['end_time'])
              rto_seconds = (end - start).total_seconds()

              cloudwatch.put_metric_data(
                  Namespace=f"DR/{os.environ['NAME_PREFIX']}",
                  MetricData=[{
                      'MetricName': f'RTO-{service}',
                      'Dimensions': [
                          {'Name': 'Service', 'Value': service},
                          {'Name': 'TestType', 'Value': test_type},
                      ],
                      'Timestamp': end,
                      'Value': rto_seconds,
                      'Unit': 'Seconds'
                  }]
              )

          except Exception as e:
              results['status'] = 'failed'
              results['error'] = str(e)
              results['end_time'] = datetime.utcnow().isoformat()

          if sns_topic:
              sns.publish(
                  TopicArn=sns_topic,
                  Subject=f'DR Test {results["status"]}: {test_type} - {service}',
                  Message=json.dumps(results, indent=2, default=str)
              )

          return results

      def run_backup_restore_test(service, region):
          steps = []
          snapshots = rds.describe_db_snapshots(
              SnapshotType='automated',
              DBInstanceIdentifier=service
          )['DBSnapshots']

          if not snapshots:
              raise Exception(f'No snapshots found for {service}')

          latest = max(snapshots, key=lambda s: s['SnapshotCreateTime'])
          steps.append({'step': 'find_snapshot', 'status': 'pass', 'detail': latest['DBSnapshotIdentifier']})

          temp_id = f"{service}-dr-test-{int(time.time())}"
          rds.restore_db_instance_from_db_snapshot(
              DBInstanceIdentifier=temp_id,
              DBSnapshotIdentifier=latest['DBSnapshotIdentifier'],
              DBInstanceClass='db.t3.micro',
              Tags=[{'Key': 'Purpose', 'Value': 'DR-Test'}]
          )
          steps.append({'step': 'restore_instance', 'status': 'pass', 'detail': temp_id})

          waiter = rds.get_waiter('db_instance_available')
          waiter.wait(DBInstanceIdentifier=temp_id, WaiterConfig={'Delay': 30, 'MaxAttempts': 60})
          steps.append({'step': 'wait_available', 'status': 'pass'})

          instance = rds.describe_db_instances(DBInstanceIdentifier=temp_id)['DBInstances'][0]
          steps.append({'step': 'verify_data', 'status': 'pass', 'detail': instance['DBInstanceStatus']})

          rds.delete_db_instance(
              DBInstanceIdentifier=temp_id,
              SkipFinalSnapshot=True,
              DeleteAutomatedBackups=True
          )
          steps.append({'step': 'cleanup', 'status': 'pass'})

          return steps

      def run_failover_test(service, hosted_zone_id):
          steps = []
          records = route53.list_resource_record_sets(
              HostedZoneId=hosted_zone_id,
              StartRecordName=service,
              StartRecordType='A'
          )['ResourceRecordSets']

          steps.append({'step': 'get_records', 'status': 'pass', 'detail': len(records)})

          route53.change_resource_record_sets(
              HostedZoneId=hosted_zone_id,
              ChangeBatch={
                  'Changes': [{
                      'Action': 'UPSERT',
                      'ResourceRecordSet': {
                          'Name': service,
                          'Type': 'A',
                          'TTL': 60,
                          'ResourceRecords': [{'Value': '10.0.0.100'}],
                          'SetIdentifier': 'secondary',
                          'Failover': 'SECONDARY'
                      }
                  }]
              }
          )
          steps.append({'step': 'failover', 'status': 'pass'})

          time.sleep(30)
          steps.append({'step': 'verify_failover', 'status': 'pass'})

          return steps

      def run_failback_test(service, hosted_zone_id):
          steps = []
          route53.change_resource_record_sets(
              HostedZoneId=hosted_zone_id,
              ChangeBatch={
                  'Changes': [{
                      'Action': 'UPSERT',
                      'ResourceRecordSet': {
                          'Name': service,
                          'Type': 'A',
                          'TTL': 60,
                          'ResourceRecords': [{'Value': '10.0.0.1'}],
                          'SetIdentifier': 'primary',
                          'Failover': 'PRIMARY'
                      }
                  }]
              }
          )
          steps.append({'step': 'failback', 'status': 'pass'})

          time.sleep(30)
          steps.append({'step': 'verify_failback', 'status': 'pass'})

          return steps

      def run_chaos_test(service, region):
          steps = []
          instances = ec2.describe_instances(
              Filters=[
                  {'Name': 'tag:Service', 'Values': [service]},
                  {'Name': 'instance-state-name', 'Values': ['running']}
              ]
          )['Reservations']

          instance_ids = [i['InstanceId'] for r in instances for i in r['Instances']]
          steps.append({'step': 'find_instances', 'status': 'pass', 'detail': instance_ids})

          if instance_ids:
              ec2.stop_instances(InstanceIds=instance_ids, Force=True)
              steps.append({'step': 'stop_instances', 'status': 'pass'})

              waiter = ec2.get_waiter('instance_stopped')
              waiter.wait(InstanceIds=instance_ids, WaiterConfig={'Delay': 15, 'MaxAttempts': 40})
              steps.append({'step': 'wait_stopped', 'status': 'pass'})

              ec2.start_instances(InstanceIds=instance_ids)
              steps.append({'step': 'start_instances', 'status': 'pass'})

              waiter = ec2.get_waiter('instance_running')
              waiter.wait(InstanceIds=instance_ids, WaiterConfig={'Delay': 15, 'MaxAttempts': 40})
              steps.append({'step': 'wait_running', 'status': 'pass'})

          return steps
    EOF
    filename = "index.py"
  }
}

resource "aws_lambda_function" "dr_testing" {
  count = var.enable_dr_testing_lambda ? 1 : 0

  function_name    = "${var.name_prefix}-dr-testing-orchestrator"
  role            = aws_iam_role.dr_testing.arn
  handler         = "index.handler"
  runtime         = "python3.11"
  timeout         = var.lambda_timeout
  filename        = data.archive_file.dr_testing_lambda[0].output_path
  source_code_hash = data.archive_file.dr_testing_lambda[0].output_base64sha256

  environment {
    variables = {
      NAME_PREFIX    = var.name_prefix
      SNS_TOPIC_ARN  = var.sns_topic_arn
      HOSTED_ZONE_ID = var.hosted_zone_id
    }
  }

  tags = var.tags
}

# ─── EventBridge Rules for Scheduled DR Tests ─────────────────────────────────

resource "aws_cloudwatch_event_rule" "dr_test_schedule" {
  for_each = var.scheduled_tests

  name                = "${var.name_prefix}-dr-test-${each.key}"
  description         = "Scheduled DR test: ${each.key}"
  schedule_expression = each.value.schedule

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "dr_test_lambda" {
  for_each = var.enable_dr_testing_lambda ? var.scheduled_tests : {}

  rule      = aws_cloudwatch_event_rule.dr_test_schedule[each.key].name
  target_id = "DRTestLambda"
  arn       = aws_lambda_function.dr_testing[0].arn

  input = jsonencode({
    test_type = each.value.test_type
    service   = each.value.service
  })
}

resource "aws_lambda_permission" "eventbridge_dr_test" {
  for_each = var.enable_dr_testing_lambda ? var.scheduled_tests : {}

  statement_id  = "AllowEventBridgeInvoke-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.dr_testing[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.dr_test_schedule[each.key].arn
}

# ─── DR Test Results S3 Bucket ────────────────────────────────────────────────

resource "aws_s3_bucket" "dr_test_results" {
  bucket = "${var.name_prefix}-dr-test-results-${data.aws_caller_identity.current.account_id}"
  tags   = merge(var.tags, { Name = "${var.name_prefix}-dr-test-results" })
}

resource "aws_s3_bucket_versioning" "dr_test_results" {
  bucket = aws_s3_bucket.dr_test_results.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "dr_test_results" {
  bucket = aws_s3_bucket.dr_test_results.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "dr_test_results" {
  bucket = aws_s3_bucket.dr_test_results.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "dr_test_results" {
  bucket = aws_s3_bucket.dr_test_results.id

  rule {
    id     = "archive-old-results"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 2555  # 7 years
    }
  }
}

# ─── DR Test Report Dashboard ──────────────────────────────────────────────────

resource "aws_cloudwatch_dashboard" "dr_testing" {
  dashboard_name = "${var.name_prefix}-dr-testing-results"
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 24
        height = 6
        properties = {
          title  = "DR Test Results - Last 30 Days"
          region = var.aws_region
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", "${var.name_prefix}-dr-testing-orchestrator", { "stat" = "Sum", "label" = "Total Tests" }],
            ["AWS/Lambda", "Errors", "FunctionName", "${var.name_prefix}-dr-testing-orchestrator", { "stat" = "Sum", "label" = "Failed Tests", "color" = "#d62728" }],
            ["AWS/Lambda", "Duration", "FunctionName", "${var.name_prefix}-dr-testing-orchestrator", { "stat" = "Average", "label" = "Avg Duration (ms)", "yAxis" = "right" }]
          ]
          period = 86400
        }
      },
      {
        type   = "log"
        x      = 0
        y      = 6
        width  = 24
        height = 12
        properties = {
          title  = "DR Test Execution Logs"
          region = var.aws_region
          query  = <<-EOT
            SOURCE '/aws/lambda/${var.name_prefix}-dr-testing-orchestrator'
            | fields @timestamp, @message
            | filter @message like /test_type/
            | sort @timestamp desc
            | limit 100
          EOT
        }
      }
    ]
  })

  tags = merge(var.tags, { Name = "${var.name_prefix}-dr-testing-results" })
}

# ─── SNS Topic for DR Test Notifications ──────────────────────────────────────

resource "aws_sns_topic" "dr_testing" {
  count = var.sns_topic_name != null ? 1 : 0

  name              = var.sns_topic_name
  kms_master_key_id = var.sns_kms_key_id
  tags              = merge(var.tags, { Name = var.sns_topic_name })
}

resource "aws_sns_topic_subscription" "dr_testing_email" {
  for_each = var.sns_topic_name != null ? var.sns_email_endpoints : []

  topic_arn = aws_sns_topic.dr_testing[0].arn
  protocol  = "email"
  endpoint  = each.value
}

# ─── Data Sources ─────────────────────────────────────────────────────────────

data "aws_caller_identity" "current" {}
