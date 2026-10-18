variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "shared_key" {
  description = "Shared key for VPN tunnels (auto-generated if empty)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "aws_vpc_id" {
  description = "AWS VPC ID"
  type        = string
  default     = null
}

variable "aws_vpc_cidr" {
  description = "AWS VPC CIDR"
  type        = string
  default     = "10.0.0.0/16"
}

variable "aws_vpn_ip_1" {
  description = "AWS VPN tunnel IP 1"
  type        = string
  default     = ""
}

variable "aws_vpn_ip_2" {
  description = "AWS VPN tunnel IP 2"
  type        = string
  default     = ""
}

variable "gcp_network_id" {
  description = "GCP network ID"
  type        = string
  default     = null
}

variable "gcp_vpc_cidr" {
  description = "GCP VPC CIDR"
  type        = string
  default     = "10.1.0.0/16"
}

variable "gcp_router_id" {
  description = "GCP Cloud Router ID"
  type        = string
  default     = null
}

variable "gcp_vpn_ip" {
  description = "GCP VPN IP address"
  type        = string
  default     = ""
}

variable "common_tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
