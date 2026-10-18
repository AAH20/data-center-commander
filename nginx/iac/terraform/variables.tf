# =============================================================================
# Data Center Commander — Load Balancer IaC Variables
# =============================================================================

variable "project_name" {
  description = "Project name used as a prefix for all resources"
  type        = string
  default     = "datacenter-commander"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "instance_type" {
  description = "EC2 instance type for LB instances"
  type        = string
  default     = "t3.medium"
}

variable "desired_capacity" {
  description = "Desired number of LB instances"
  type        = number
  default     = 2
}

variable "min_size" {
  description = "Minimum number of LB instances"
  type        = number
  default     = 2
}

variable "max_size" {
  description = "Maximum number of LB instances"
  type        = number
  default     = 6
}

variable "load_balancer_type" {
  description = "Type of load balancer to deploy (nginx or traefik)"
  type        = string
  default     = "nginx"

  validation {
    condition     = contains(["nginx", "traefik"], var.load_balancer_type)
    error_message = "Load balancer type must be nginx or traefik."
  }
}

variable "acm_certificate_arn" {
  description = "ARN of the ACM certificate for HTTPS"
  type        = string
  default     = ""
}

variable "enable_stickiness" {
  description = "Enable session stickiness on the ALB target group"
  type        = bool
  default     = false
}

variable "common_tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default = {
    Project   = "data-center-commander"
    ManagedBy = "terraform"
  }
}
