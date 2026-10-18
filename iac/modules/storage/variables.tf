variable "bucket_name" {
  description = "Base name for storage buckets"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "enable_aws" {
  description = "Enable AWS S3"
  type        = bool
  default     = false
}

variable "enable_gcp" {
  description = "Enable GCP Cloud Storage"
  type        = bool
  default     = false
}

variable "enable_azure" {
  description = "Enable Azure Blob Storage"
  type        = bool
  default     = false
}

variable "enable_versioning" {
  description = "Enable object versioning"
  type        = bool
  default     = true
}

variable "enable_encryption" {
  description = "Enable server-side encryption"
  type        = bool
  default     = true
}

variable "storage_class" {
  description = "GCP storage class"
  type        = string
  default     = "STANDARD"
}

variable "gcp_location" {
  description = "GCP storage location"
  type        = string
  default     = "US"
}

variable "gcp_kms_key" {
  description = "GCP KMS key for encryption"
  type        = string
  default     = ""
}

variable "azure_resource_group" {
  description = "Azure resource group name"
  type        = string
  default     = ""
}

variable "azure_location" {
  description = "Azure region"
  type        = string
  default     = "East US"
}

variable "azure_replication_type" {
  description = "Azure storage replication type"
  type        = string
  default     = "GRS"
}

variable "common_tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
