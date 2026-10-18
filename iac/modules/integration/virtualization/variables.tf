variable "cluster_name" {
  description = "Name prefix for all virtualization resources"
  type        = string
}

variable "environment" {
  description = "Environment label (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "pool_name" {
  description = "Libvirt storage pool name"
  type        = string
  default     = "data-center-pool"
}

variable "pool_path" {
  description = "Host path for the libvirt storage pool"
  type        = string
  default     = "/var/lib/libvirt/images/data-center"
}

variable "network_name" {
  description = "Libvirt virtual network name"
  type        = string
  default     = "data-center-net"
}

variable "network_domain" {
  description = "DNS domain for the virtual network"
  type        = string
  default     = "datacenter.local"
}

variable "network_cidr" {
  description = "CIDR for the virtual network"
  type        = string
  default     = "10.10.0.0/24"
}

variable "base_image_path" {
  description = "Path to the base QCOW2 image (golden image)"
  type        = string
}

variable "vm_count" {
  description = "Number of VMs to provision"
  type        = number
  default     = 3

  validation {
    condition     = var.vm_count > 0 && var.vm_count <= 20
    error_message = "VM count must be between 1 and 20."
  }
}

variable "vm_memory_mb" {
  description = "Memory per VM in MB"
  type        = number
  default     = 4096
}

variable "vm_vcpu_count" {
  description = "vCPUs per VM"
  type        = number
  default     = 2
}

variable "vm_disk_size" {
  description = "Disk size per VM in GB"
  type        = number
  default     = 50
}

variable "ssh_public_key" {
  description = "SSH public key injected into VMs via cloud-init"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
