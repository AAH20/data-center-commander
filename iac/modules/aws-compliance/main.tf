terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "compliance_s3_bucket" {
  description = "S3 bucket for compliance logs (CloudTrail, AWS Config)"
  type        = string
}

variable "compliance_kms_key_id" {
  description = "KMS key ID for encrypting compliance logs"
  type        = string
  default     = null
}

# --- AWS Config ---
module "aws_config" {
  source = "./aws-config"

  config_s3_bucket_name = var.compliance_s3_bucket
  config_s3_key_prefix  = "config"

  managed_rules = [
    {
      name            = "s3-bucket-public-read-prohibited"
      rule_identifier = "S3_BUCKET_PUBLIC_READ_PROHIBITED"
    },
    {
      name            = "s3-bucket-public-write-prohibited"
      rule_identifier = "S3_BUCKET_PUBLIC_WRITE_PROHIBITED"
    },
    {
      name            = "rds-storage-encrypted"
      rule_identifier = "RDS_STORAGE_ENCRYPTED"
    },
    {
      name            = "ec2-volume-inuse-check"
      rule_identifier = "EC2_VOLUME_INUSE_CHECK"
    },
    {
      name            = "iam-password-policy"
      rule_identifier = "IAM_PASSWORD_POLICY"
      input_parameters = jsonencode({
        RequireUppercaseCharacters = true
        RequireLowercaseCharacters = true
        RequireSymbols             = true
        RequireNumbers             = true
        MinimumPasswordLength      = 14
        PasswordReusePrevention    = 24
        MaxPasswordAge             = 90
      })
    },
    {
      name            = "root-account-mfa-enabled"
      rule_identifier = "ROOT_ACCOUNT_MFA_ENABLED"
    },
    {
      name            = "iam-user-no-policies-check"
      rule_identifier = "IAM_USER_NO_POLICIES_CHECK"
    },
    {
      name            = "security-group-open-to-world"
      rule_identifier = "INSECURE_SECURITY_GROUP_RULES"
    }
  ]

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# --- GuardDuty ---
module "guardduty" {
  source = "./guardduty"

  detector_finding_publishing_frequency = "SIX_HOURS"

  data_sources = {
    s3_logs            = true
    kubernetes         = true
    malware_protection = true
  }

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# --- Security Hub ---
module "security_hub" {
  source = "./security-hub"

  enable_security_hub       = true
  auto_enable_new_standards = true

  enable_standards = [
    { name = "aws-foundational-security-best-practices", version = "v1.0.0" },
    { name = "cis-aws-foundations-benchmark", version = "v1.4.0" },
    { name = "pci-dss", version = "v3.2.1" }
  ]

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# --- CloudTrail ---
module "cloudtrail" {
  source = "./cloudtrail"

  trail_name                    = "compliance-trail"
  s3_bucket_name                = var.compliance_s3_bucket
  s3_key_prefix                 = "cloudtrail"
  enable_log_file_validation    = true
  is_multi_region_trail         = true
  include_global_service_events = true
  kms_key_id                    = var.compliance_kms_key_id

  event_selectors = [
    {
      read_write_type           = "All"
      include_management_events = true
      data_resources = [
        {
          type   = "AWS::S3::Object"
          values = ["arn:aws:s3:::"]
        },
        {
          type   = "AWS::Lambda::Function"
          values = ["arn:aws:lambda"]
        }
      ]
    }
  ]

  insight_selectors = [
    { insight_type = "ApiCallRateInsight" },
    { insight_type = "ApiErrorRateInsight" }
  ]

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# --- IAM Access Analyzer ---
module "iam_access_analyzer" {
  source = "./iam-access-analyzer"

  analyzer_name         = "compliance-analyzer"
  analyzer_type         = "ACCOUNT"
  unused_access_enabled = true
  unused_access_age     = 90

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# --- Outputs ---
output "config_recorder_id" {
  value = module.aws_config.config_recorder_id
}

output "guardduty_detector_id" {
  value = module.guardduty.detector_id
}

output "security_hub_arn" {
  value = module.security_hub.security_hub_arn
}

output "cloudtrail_arn" {
  value = module.cloudtrail.trail_arn
}

output "access_analyzer_arn" {
  value = module.iam_access_analyzer.analyzer_arn
}
