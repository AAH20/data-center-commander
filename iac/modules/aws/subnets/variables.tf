variable "name" {
  description = "Name prefix for subnet resources"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "public_subnet_cidrs" {
  description = "List of CIDR blocks for public subnets"
  type        = list(string)
  default     = []
}

variable "private_subnet_cidrs" {
  description = "List of CIDR blocks for private subnets"
  type        = list(string)
  default     = []
}

variable "database_subnet_cidrs" {
  description = "List of CIDR blocks for database subnets"
  type        = list(string)
  default     = []
}

variable "availability_zones" {
  description = "List of AZs (auto-detected if null)"
  type        = list(string)
  default     = null
}

variable "internet_gateway_id" {
  description = "ID of the Internet Gateway for public route table"
  type        = string
  default     = null
}

variable "enable_nat_gateway" {
  description = "Create a NAT gateway for private subnet outbound access"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
