variable "vnet_name" {
  description = "Name of the virtual network"
  type        = string
}

variable "vnet_cidr" {
  description = "Address space for the VNet"
  type        = string
  default     = "10.2.0.0/16"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "East US"
}

variable "enable_public_ip" {
  description = "Create a public IP"
  type        = bool
  default     = true
}

variable "enable_network_watcher" {
  description = "Enable Network Watcher"
  type        = bool
  default     = true
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "common_tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
