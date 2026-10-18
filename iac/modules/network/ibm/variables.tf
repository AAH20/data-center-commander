variable "vpc_name" {
  description = "Name of the VPC"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.3.0.0/16"
}

variable "region" {
  description = "IBM Cloud region"
  type        = string
  default     = "us-south"
}

variable "resource_group_id" {
  description = "IBM Cloud resource group ID"
  type        = string
  default     = ""
}

variable "enable_public_gateway" {
  description = "Enable public gateway for the subnet"
  type        = bool
  default     = true
}

variable "enable_ssh" {
  description = "Allow SSH inbound"
  type        = bool
  default     = true
}

variable "enable_http" {
  description = "Allow HTTP inbound"
  type        = bool
  default     = true
}

variable "enable_https" {
  description = "Allow HTTPS inbound"
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
