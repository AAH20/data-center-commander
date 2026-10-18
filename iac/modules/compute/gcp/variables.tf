variable "instance_name" {
  description = "Name prefix for compute instances"
  type        = string
}

variable "machine_type" {
  description = "GCP machine type"
  type        = string
  default     = "e2-medium"
}

variable "instance_count" {
  description = "Number of compute instances"
  type        = number
  default     = 1
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "zones" {
  description = "List of zones to distribute instances across"
  type        = list(string)
  default     = ["a", "b", "c"]
}

variable "network_id" {
  description = "VPC network ID"
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID"
  type        = string
}

variable "boot_disk_size" {
  description = "Boot disk size in GB"
  type        = number
  default     = 20
}

variable "enable_encryption" {
  description = "Enable disk encryption"
  type        = bool
  default     = true
}

variable "kms_key_id" {
  description = "KMS key ID for disk encryption"
  type        = string
  default     = ""
}

variable "enable_static_ip" {
  description = "Assign static external IPs"
  type        = bool
  default     = false
}

variable "enable_monitoring" {
  description = "Enable monitoring"
  type        = bool
  default     = true
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "common_tags" {
  description = "Labels to apply to all resources"
  type        = map(string)
  default     = {}
}
