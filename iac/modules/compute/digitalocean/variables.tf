variable "droplet_name" {
  description = "Name prefix for droplets"
  type        = string
}

variable "size" {
  description = "Droplet size slug"
  type        = string
  default     = "s-2vcpu-4gb"
}

variable "image" {
  description = "Droplet image slug or ID"
  type        = string
  default     = "ubuntu-22-04-x64"
}

variable "region" {
  description = "DigitalOcean region slug"
  type        = string
  default     = "nyc3"
}

variable "instance_count" {
  description = "Number of droplets"
  type        = number
  default     = 1
}

variable "ssh_key_names" {
  description = "Names of SSH keys in DigitalOcean"
  type        = list(string)
  default     = []
}

variable "enable_monitoring" {
  description = "Enable DigitalOcean monitoring"
  type        = bool
  default     = true
}

variable "enable_firewall" {
  description = "Create a cloud firewall"
  type        = bool
  default     = true
}

variable "project_name" {
  description = "DigitalOcean project name to assign droplets to"
  type        = string
  default     = ""
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
