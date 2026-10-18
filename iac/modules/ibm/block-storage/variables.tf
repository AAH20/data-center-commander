variable "name" {
  description = "Name of the block storage volume"
  type        = string
}

variable "zone" {
  description = "Zone for the volume (e.g., us-south-1)"
  type        = string
}

variable "capacity" {
  description = "Volume capacity in GB"
  type        = number
  default     = 100
}

variable "profile" {
  description = "Storage profile (e.g., 10iops-tier, 5iops-tier, general-purpose)"
  type        = string
  default     = "10iops-tier"

  validation {
    condition     = contains(["10iops-tier", "5iops-tier", "general-purpose", "custom"], var.profile)
    error_message = "Must be 10iops-tier, 5iops-tier, general-purpose, or custom."
  }
}

variable "instance_id" {
  description = "ID of the VSI to attach this volume to (optional)"
  type        = string
  default     = null
}

variable "delete_on_instance_delete" {
  description = "Delete volume when attached instance is deleted"
  type        = bool
  default     = false
}

variable "encryption_key_crn" {
  description = "CRN of the encryption key (optional, for customer-managed encryption)"
  type        = string
  default     = null
}

variable "resource_group_id" {
  description = "IBM Cloud resource group ID"
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = list(string)
  default     = []
}
