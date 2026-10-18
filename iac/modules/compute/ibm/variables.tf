variable "instance_name" {
  description = "Name prefix for VPC instances"
  type        = string
}

variable "instance_profile" {
  description = "IBM VPC instance profile"
  type        = string
  default     = "bx2-2x8"
}

variable "instance_count" {
  description = "Number of instances"
  type        = number
  default     = 1
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID"
  type        = string
}

variable "security_group_id" {
  description = "Security group ID"
  type        = string
}

variable "region" {
  description = "IBM Cloud region"
  type        = string
  default     = "us-south"
}

variable "zones" {
  description = "List of zones"
  type        = list(string)
  default     = ["1", "2", "3"]
}

variable "ssh_key_ids" {
  description = "List of SSH key IDs"
  type        = list(string)
  default     = []
}

variable "resource_group_id" {
  description = "IBM Cloud resource group ID"
  type        = string
  default     = ""
}

variable "enable_floating_ip" {
  description = "Assign floating IPs to instances"
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
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
