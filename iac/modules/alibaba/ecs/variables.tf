variable "name" {
  description = "Name prefix for the ECS instances"
  type        = string
}

variable "count" {
  description = "Number of ECS instances to create"
  type        = number
  default     = 1

  validation {
    condition     = var.count > 0
    error_message = "Count must be greater than 0."
  }
}

variable "instance_type" {
  description = "Instance type for the ECS instances"
  type        = string
  default     = "ecs.g7.large"
}

variable "image_name" {
  description = "Name pattern of the OS image"
  type        = string
  default     = "ubuntu_22_04_x64_*"
}

variable "vswitch_id" {
  description = "VSwitch ID to attach the instances to"
  type        = string
}

variable "security_group_ids" {
  description = "List of security group IDs to attach"
  type        = list(string)
  default     = []
}

variable "availability_zone" {
  description = "Availability zone for the instances"
  type        = string
  default     = null
}

variable "system_disk_category" {
  description = "System disk category"
  type        = string
  default     = "cloud_essd"

  validation {
    condition     = contains(["cloud_efficiency", "cloud_ssd", "cloud_essd", "cloud_auto"], var.system_disk_category)
    error_message = "Must be a valid disk category."
  }
}

variable "system_disk_size" {
  description = "System disk size in GB"
  type        = number
  default     = 40
}

variable "data_disk_category" {
  description = "Data disk category"
  type        = string
  default     = "cloud_essd"
}

variable "data_disk_size" {
  description = "Data disk size in GB"
  type        = number
  default     = 100
}

variable "internet_max_bandwidth_out" {
  description = "Maximum outbound bandwidth in Mbps"
  type        = number
  default     = 0
}

variable "key_name" {
  description = "SSH key pair name"
  type        = string
  default     = null
}

variable "enable_eip" {
  description = "Associate an Elastic IP"
  type        = bool
  default     = false
}

variable "eip_bandwidth" {
  description = "EIP bandwidth in Mbps"
  type        = number
  default     = 5
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
