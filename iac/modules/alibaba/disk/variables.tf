variable "name" {
  description = "Name prefix for the disks"
  type        = string
}

variable "count" {
  description = "Number of disks to create"
  type        = number
  default     = 1

  validation {
    condition     = var.count > 0
    error_message = "Count must be greater than 0."
  }
}

variable "size" {
  description = "Disk size in GB"
  type        = number
  default     = 100

  validation {
    condition     = var.size >= 20
    error_message = "Size must be at least 20 GB."
  }
}

variable "category" {
  description = "Disk category"
  type        = string
  default     = "cloud_essd"

  validation {
    condition     = contains(["cloud_efficiency", "cloud_ssd", "cloud_essd", "cloud_auto"], var.category)
    error_message = "Must be a valid disk category."
  }
}

variable "zone_id" {
  description = "Zone ID for the disks"
  type        = string
}

variable "description" {
  description = "Description of the disks"
  type        = string
  default     = ""
}

variable "instance_id" {
  description = "ID of the ECS instance to attach disks to (optional)"
  type        = string
  default     = null
}

variable "encrypted" {
  description = "Enable encryption for the disks"
  type        = bool
  default     = false
}

variable "kms_key_id" {
  description = "KMS key ID for encryption (required if encrypted is true)"
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
