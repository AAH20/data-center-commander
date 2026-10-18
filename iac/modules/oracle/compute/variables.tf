variable "compartment_id" {
  description = "OCID of the compartment"
  type        = string
}

variable "name" {
  description = "Name prefix for the compute instances"
  type        = string
}

variable "count" {
  description = "Number of compute instances to create"
  type        = number
  default     = 1

  validation {
    condition     = var.count > 0
    error_message = "Count must be greater than 0."
  }
}

variable "shape" {
  description = "Shape for the compute instances"
  type        = string
  default     = "VM.Standard.E4.Flex"
}

variable "availability_domain" {
  description = "Availability domain for the instances"
  type        = string
  default     = null
}

variable "subnet_id" {
  description = "Subnet ID to attach the instances to"
  type        = string
}

variable "assign_public_ip" {
  description = "Assign a public IP to the instances"
  type        = bool
  default     = false
}

variable "nsg_ids" {
  description = "List of network security group IDs"
  type        = list(string)
  default     = []
}

variable "operating_system" {
  description = "Operating system for the image"
  type        = string
  default     = "Oracle Linux"
}

variable "operating_system_version" {
  description = "Operating system version"
  type        = string
  default     = "9"
}

variable "boot_volume_size" {
  description = "Boot volume size in GB"
  type        = number
  default     = 50
}

variable "ssh_authorized_keys" {
  description = "SSH public key for the instances"
  type        = string
  default     = null
}

variable "user_data" {
  description = "User data for cloud-init"
  type        = string
  default     = null
}

variable "preserve_boot_volume" {
  description = "Preserve boot volume on termination"
  type        = bool
  default     = false
}

variable "create_vnic" {
  description = "Create an additional VNIC"
  type        = bool
  default     = false
}

variable "additional_subnet_id" {
  description = "Subnet ID for the additional VNIC"
  type        = string
  default     = null
}

variable "additional_nsg_ids" {
  description = "NSG IDs for the additional VNIC"
  type        = list(string)
  default     = []
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
