terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# GuardDuty Detector
resource "aws_guardduty_detector" "this" {
  enable = var.detector_enable

  datasources {
    s3_logs {
      enable = lookup(var.data_sources, "s3_logs", true)
    }

    kubernetes {
      audit_logs {
        enable = lookup(var.data_sources, "kubernetes", true)
      }
    }

    # Malware protection is expressed in the AWS provider as EBS volume
    # scanning: `scan_ec2_instance_with_findings` requires an `ebs_volumes`
    # block, and `enable` lives on that block (there is no `enable` argument
    # directly on `scan_ec2_instance_with_findings`).
    malware_protection {
      scan_ec2_instance_with_findings {
        ebs_volumes {
          enable = lookup(var.data_sources, "malware_protection", true)
        }
      }
    }
  }

  finding_publishing_frequency = var.detector_finding_publishing_frequency

  tags = var.tags
}

# GuardDuty Member Invitations
resource "aws_guardduty_member" "this" {
  for_each = { for member in var.members : member.account_id => member }

  detector_id = aws_guardduty_detector.this.id
  account_id  = each.value.account_id
  email       = each.value.email
  invite      = each.value.invite

  depends_on = [aws_guardduty_detector.this]
}

# GuardDuty Publishing Destination (S3)
resource "aws_guardduty_publishing_destination" "this" {
  count = var.publishing_destination_s3_arn != null ? 1 : 0

  detector_id     = aws_guardduty_detector.this.id
  destination_arn = var.publishing_destination_s3_arn
  kms_key_arn     = var.publishing_destination_kms_key_arn

  depends_on = [aws_guardduty_detector.this]
}
