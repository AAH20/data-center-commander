variable "name" {
  description = "Name of the VSI instance"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "subnet_id" {
  description = "ID of the subnet"
  type        = string
}

variable "zone" {
  description = "Zone for the VSI (e.g., us-south-1)"
  type        = string
}

variable "profile" {
  description = "Instance profile (e.g., bx2-2x8, cx2-2x4)"
  type        = string
  default     = "bx2-2x8"
}

variable "image_name" {
  description = "Name of the OS image (e.g., ibm-ubuntu-22-04-1-amd64-1)"
  type        = string
  default     = "ibm-ubuntu-22-04-1-amd64-1"
}

variable "ssh_key_ids" {
  description = "List of SSH key names to attach"
  type        = list(string)
  default     = []
}

variable "security_group_ids" {
  description = "List of security group IDs to attach"
  type        = list(string)
  default     = []
}

variable "boot_volume_size" {
  description = "Boot volume size in GB"
  type        = number
  default     = 100
}

variable "data_volume_ids" {
  description = "List of data volume IDs to attach"
  type        = list(string)
  default     = []
}

variable "resource_group_id" {
  description = "IBM Cloud resource group ID"
  type        = string
  default     = null
}

variable "enable_floating_ip" {
  description = "Assign a floating IP to the VSI"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = list(string)
  default     = []
}
