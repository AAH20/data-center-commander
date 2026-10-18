terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# AWS Config Configuration Recorder
resource "aws_config_configuration_recorder" "this" {
  name     = var.config_recorder_name
  role_arn = aws_iam_role.config.arn

  recording_group {
    all_supported                 = var.config_all_supported
    include_global_resource_types = var.config_include_global_resource_types
  }
}

# AWS Config Delivery Channel
resource "aws_config_delivery_channel" "this" {
  name           = var.config_delivery_channel_name
  s3_bucket_name = var.config_s3_bucket_name
  s3_key_prefix  = var.config_s3_key_prefix
  sns_topic_arn  = var.config_sns_topic_arn

  snapshot_delivery_properties {
    delivery_frequency = var.config_recording_frequency
  }

  depends_on = [aws_config_configuration_recorder.this]
}

# Start the configuration recorder
resource "aws_config_configuration_recorder_status" "this" {
  name       = aws_config_configuration_recorder.this.name
  is_enabled = true

  depends_on = [aws_config_delivery_channel.this]
}

# IAM Role for AWS Config
resource "aws_iam_role" "config" {
  name = "aws-config-role-${data.aws_caller_identity.current.account_id}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "config.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# IAM Policy for AWS Config
resource "aws_iam_role_policy" "config" {
  name = "aws-config-policy"
  role = aws_iam_role.config.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl"
        ]
        Resource = "arn:aws:s3:::${var.config_s3_bucket_name}/config/*"
        Condition = {
          StringLike = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetBucketAcl"
        ]
        Resource = "arn:aws:s3:::${var.config_s3_bucket_name}"
      },
      {
        Effect = "Allow"
        Action = [
          "config:Put*",
          "config:Get*",
          "config:List*",
          "config:Describe*",
          "config:StartConfigurationRecorder",
          "config:StopConfigurationRecorder",
          "config:DeleteConfigurationRecorder",
          "config:PutConfigurationRecorder",
          "config:PutDeliveryChannel",
          "config:DeleteDeliveryChannel",
          "config:PutEvaluations",
          "config:SelectResourceConfig"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = var.config_sns_topic_arn != null ? var.config_sns_topic_arn : "*"
      }
    ]
  })
}

# AWS Config Managed Rules
resource "aws_config_config_rule" "managed" {
  for_each = { for rule in var.managed_rules : rule.name => rule }

  name        = each.value.name
  description = "Managed rule: ${each.value.rule_identifier}"

  source {
    owner             = "AWS"
    source_identifier = each.value.rule_identifier
  }

  input_parameters = each.value.input_parameters

  maximum_execution_frequency = each.value.compliance_severity

  tags = var.tags

  depends_on = [aws_config_configuration_recorder.this]
}

# AWS Config Custom Rules (Lambda-backed)
resource "aws_config_config_rule" "custom" {
  for_each = { for rule in var.custom_rules : rule.name => rule }

  name        = each.value.name
  description = each.value.description

  source {
    owner             = each.value.source_owner
    source_identifier = each.value.source_identifier

    dynamic "source_detail" {
      for_each = each.value.source_detail != null ? [each.value.source_detail] : []
      content {
        event_source                = lookup(source_detail.value, "event_source", "aws.config")
        maximum_execution_frequency = lookup(source_detail.value, "maximum_execution_frequency", null)
        message_type                = lookup(source_detail.value, "message_type", null)
      }
    }
  }

  input_parameters = each.value.input_parameters

  maximum_execution_frequency = each.value.maximum_execution_frequency

  dynamic "scope" {
    for_each = each.value.scope != null ? [each.value.scope] : []
    content {
      compliance_resource_id    = lookup(scope.value, "compliance_resource_id", null)
      compliance_resource_types = lookup(scope.value, "compliance_resource_types", null)
      tag_key                    = lookup(scope.value, "tag_key", null)
      tag_value                  = lookup(scope.value, "tag_value", null)
    }
  }

  tags = var.tags

  depends_on = [aws_config_configuration_recorder.this]
}

# AWS Config Aggregator (optional)
resource "aws_config_configuration_aggregator" "this" {
  count = var.config_aggregator_name != null ? 1 : 0

  name = var.config_aggregator_name

  dynamic "account_aggregation_source" {
    for_each = length(var.config_aggregator_account_ids) > 0 ? [1] : []
    content {
      account_ids = var.config_aggregator_account_ids
      regions     = [data.aws_region.current.name]
    }
  }

  dynamic "organization_aggregation_source" {
    for_each = var.config_aggregator_organization ? [1] : []
    content {
      all_regions = true
      role_arn    = aws_iam_role.config_aggregator[0].arn
    }
  }

  tags = var.tags
}

# IAM Role for Config Aggregator (organization-level)
resource "aws_iam_role" "config_aggregator" {
  count = var.config_aggregator_organization ? 1 : 0

  name = "aws-config-aggregator-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "config.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "config_aggregator" {
  count = var.config_aggregator_organization ? 1 : 0

  name = "aws-config-aggregator-policy"
  role = aws_iam_role.config_aggregator[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "organizations:DescribeOrganization",
          "organizations:ListAccounts",
          "organizations:ListDelegatedAdministrators"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "config:Put*",
          "config:Get*",
          "config:List*",
          "config:Describe*"
        ]
        Resource = "*"
      }
    ]
  })
}
