variable "name" {
  description = "Name prefix for the volumes"
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

variable "disk_offering" {
  description = "Disk offering (size/type)"
  type        = string
}

variable "zone_id" {
  description = "Zone ID"
  type        = string
}

variable "attach" {
  description = "Attach the disk to a VM"
  type        = bool
  default     = false
}

variable "virtual_machine_id" {
  description = "VM ID to attach the disk to"
  type        = string
  default     = null
}

variable "size" {
  description = "Disk size in GB"
  type        = number
  default     = null
}

variable "create_volume" {
  description = "Create a standalone volume"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
