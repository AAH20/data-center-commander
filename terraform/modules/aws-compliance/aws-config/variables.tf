variable "config_recorder_name" {
  description = "Name of the AWS Config configuration recorder"
  type        = string
  default     = "default"
}

variable "config_delivery_channel_name" {
  description = "Name of the AWS Config delivery channel"
  type        = string
  default     = "default"
}

variable "config_s3_bucket_name" {
  description = "Name of the S3 bucket for AWS Config delivery"
  type        = string
}

variable "config_s3_key_prefix" {
  description = "S3 key prefix for AWS Config delivery"
  type        = string
  default     = "config"
}

variable "config_sns_topic_arn" {
  description = "ARN of the SNS topic for AWS Config notifications"
  type        = string
  default     = null
}

variable "config_recording_frequency" {
  description = "Frequency of AWS Config configuration snapshots"
  type        = string
  default     = "TwentyFour_Hours"
}

variable "config_all_supported" {
  description = "Record all supported resource types"
  type        = bool
  default     = true
}

variable "config_include_global_resource_types" {
  description = "Include global resource types in recording"
  type        = bool
  default     = true
}

variable "config_aggregator_name" {
  description = "Name of the AWS Config aggregator (optional)"
  type        = string
  default     = null
}

variable "config_aggregator_account_ids" {
  description = "List of account IDs for AWS Config aggregation"
  type        = list(string)
  default     = []
}

variable "config_aggregator_organization" {
  description = "Enable organization-wide AWS Config aggregation"
  type        = bool
  default     = false
}

variable "managed_rules" {
  description = "List of AWS Config managed rules to enable"
  type = list(object({
    name                = string
    rule_identifier     = string
    input_parameters    = optional(map(string), {})
    compliance_severity = optional(string, "TwentyFour_Hours")
  }))
  default = [
    {
      name                = "s3-bucket-server-side-encryption-enabled"
      rule_identifier     = "S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED"
      input_parameters    = {}
      compliance_severity = "TwentyFour_Hours"
    },
    {
      name                = "s3-bucket-public-read-prohibited"
      rule_identifier     = "S3_BUCKET_PUBLIC_READ_PROHIBITED"
      input_parameters    = {}
      compliance_severity = "TwentyFour_Hours"
    },
    {
      name                = "rds-storage-encrypted"
      rule_identifier     = "RDS_STORAGE_ENCRYPTED"
      input_parameters    = {}
      compliance_severity = "TwentyFour_Hours"
    },
    {
      name                = "vpc-flow-logs-enabled"
      rule_identifier     = "VPC_FLOW_LOGS_ENABLED"
      input_parameters    = {}
      compliance_severity = "TwentyFour_Hours"
    },
    {
      name                = "iam-password-policy"
      rule_identifier     = "IAM_PASSWORD_POLICY"
      input_parameters = {
        RequireUppercaseCharacters = "true"
        RequireLowercaseCharacters = "true"
        RequireSymbols             = "true"
        RequireNumbers             = "true"
        MinimumPasswordLength      = "12"
        PasswordReusePrevention    = "24"
        MaxPasswordAge             = "90"
      }
      compliance_severity = "TwentyFour_Hours"
    },
    {
      name                = "cloudtrail-enabled"
      rule_identifier     = "CLOUD_TRAIL_ENABLED"
      input_parameters    = {}
      compliance_severity = "TwentyFour_Hours"
    },
    {
      name                = "ec2-instance-imdsv2-required"
      rule_identifier     = "EC2_INSTANCE_IMDSV2_REQUIRED"
      input_parameters    = {}
      compliance_severity = "TwentyFour_Hours"
    },
    {
      name                = "kms-key-rotation-enabled"
      rule_identifier     = "KMS_KEY_ROTATION_ENABLED"
      input_parameters    = {}
      compliance_severity = "TwentyFour_Hours"
    },
  ]
}

variable "custom_rules" {
  description = "List of AWS Config custom rules (Lambda-backed)"
  type = list(object({
    name                        = string
    description                 = string
    source_owner                = string
    source_identifier           = string
    source_detail               = optional(any)
    input_parameters            = optional(map(string), {})
    maximum_execution_frequency = optional(string, "TwentyFour_Hours")
    scope                       = optional(any)
  }))
  default = []
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
