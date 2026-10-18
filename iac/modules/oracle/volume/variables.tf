variable "compartment_id" {
  description = "OCID of the compartment"
  type        = string
}

variable "name" {
  description = "Name prefix for the volumes"
  type        = string
}

variable "count" {
  description = "Number of volumes to create"
  type        = number
  default     = 1

  validation {
    condition     = var.count > 0
    error_message = "Count must be greater than 0."
  }
}

variable "availability_domain" {
  description = "Availability domain for the volumes"
  type        = string
}

variable "size_in_gbs" {
  description = "Volume size in GB"
  type        = number
  default     = 50

  validation {
    condition     = var.size_in_gbs >= 50
    error_message = "Size must be at least 50 GB."
  }
}

variable "vpus_per_gb" {
  description = "VPUs per GB (performance tier)"
  type        = number
  default     = 10

  validation {
    condition     = contains([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120], var.vpus_per_gb)
    error_message = "Must be a valid VPUs per GB value."
  }
}

variable "instance_id" {
  description = "ID of the compute instance to attach volumes to (optional)"
  type        = string
  default     = null
}

variable "attachment_type" {
  description = "Attachment type"
  type        = string
  default     = "paravirtualized"

  validation {
    condition     = contains(["paravirtualized", "iscsi"], var.attachment_type)
    error_message = "Must be paravirtualized or iscsi."
  }
}

variable "device" {
  description = "Device path for the volume"
  type        = string
  default     = null
}

variable "is_read_only" {
  description = "Mount the volume as read-only"
  type        = bool
  default     = false
}

variable "replica_availability_domain" {
  description = "Availability domain for block volume replicas"
  type        = string
  default     = null
}

variable "create_backup_policy" {
  description = "Create a backup policy"
  type        = bool
  default     = false
}

variable "defined_tags" {
  description = "Defined tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "freeform_tags" {
  description = "Freeform tags to apply to all resources"
  type        = map(string)
  default     = {}
}
