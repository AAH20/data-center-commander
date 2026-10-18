variable "name" {
  description = "Name prefix for the EVS volumes"
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

variable "size" {
  description = "Volume size in GB"
  type        = number
  default     = 100

  validation {
    condition     = var.size >= 10
    error_message = "Size must be at least 10 GB."
  }
}

variable "volume_type" {
  description = "Volume type"
  type        = string
  default     = "SAS"

  validation {
    condition     = contains(["SAS", "SSD", "GPSSD", "ESSD"], var.volume_type)
    error_message = "Must be SAS, SSD, GPSSD, or ESSD."
  }
}

variable "availability_zone" {
  description = "Availability zone for the volumes"
  type        = string
}

variable "description" {
  description = "Description of the volumes"
  type        = string
  default     = ""
}

variable "instance_id" {
  description = "ID of the ECS instance to attach volumes to (optional)"
  type        = string
  default     = null
}

variable "multiattach" {
  description = "Enable multi-attach for the volumes"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
