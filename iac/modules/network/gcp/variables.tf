variable "network_name" {
  description = "Name of the VPC network"
  type        = string
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

variable "vpc_cidr" {
  description = "CIDR block for the VPC (used for subnet)"
  type        = string
  default     = "10.1.0.0/16"
}

variable "subnet_cidr" {
  description = "CIDR block for the subnet"
  type        = string
  default     = "10.1.1.0/24"
}

variable "enable_cloud_nat" {
  description = "Enable Cloud NAT for outbound connectivity"
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

# This module owns its google provider configuration (see providers.tf) so that
# it can apply `common_tags` as provider-level `default_labels`. Terraform
# forbids count/for_each/depends_on on calls to a module that configures its
# own providers, so the "deploy this cloud or not" switch lives here instead of
# on the caller's module block.
variable "enabled" {
  description = "Whether to create the network resources (false creates nothing, but keeps the module instantiable)"
  type        = bool
  default     = true
}
