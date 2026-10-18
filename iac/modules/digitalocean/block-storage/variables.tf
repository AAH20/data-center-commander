variable "name" {
  description = "Name prefix for the Block Storage volumes"
  type        = string
}

variable "count" {
  description = "Number of Block Storage volumes to create"
  type        = number
  default     = 1

  validation {
    condition     = var.count > 0
    error_message = "Count must be greater than 0."
  }
}

variable "region" {
  description = "Region where the Block Storage volumes will be created"
  type        = string
}

variable "size" {
  description = "Size of each Block Storage volume in GiB"
  type        = number

  validation {
    condition     = var.size >= 1
    error_message = "Size must be at least 1 GiB."
  }
}

variable "description" {
  description = "Description of the Block Storage volumes"
  type        = string
  default     = ""
}

variable "filesystem_type" {
  description = "Filesystem type for the volumes (ext4, xfs)"
  type        = string
  default     = "ext4"

  validation {
    condition     = contains(["ext4", "xfs"], var.filesystem_type)
    error_message = "Filesystem type must be ext4 or xfs."
  }
}

variable "filesystem_label" {
  description = "Filesystem label for the volumes"
  type        = string
  default     = null
}

variable "initial_filesystem_type" {
  description = "Initial filesystem type for the volumes"
  type        = string
  default     = null
}

variable "initial_filesystem_label" {
  description = "Initial filesystem label for the volumes"
  type        = string
  default     = null
}

variable "snapshot_id" {
  description = "Snapshot ID to create the volumes from"
  type        = string
  default     = null
}

variable "attach_to_droplets" {
  description = "Whether to attach the volumes to Droplets"
  type        = bool
  default     = false
}

variable "droplet_ids" {
  description = "List of Droplet IDs to attach the volumes to (required if attach_to_droplets is true)"
  type        = list(number)
  default     = []
}

variable "prevent_destroy" {
  description = "Prevent accidental destruction of the volumes"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to the Block Storage volumes"
  type        = list(string)
  default     = []
}
