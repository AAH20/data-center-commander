variable "project_id" {
  description = "GCP project ID to apply organization policies to"
  type        = string
}

variable "disable_serial_port" {
  description = "Disable serial port access on VMs"
  type        = bool
  default     = true
}

variable "require_os_login" {
  description = "Require OS Login for SSH access"
  type        = bool
  default     = true
}

variable "restrict_vm_external_ips" {
  description = "Restrict external IPs on VM instances"
  type        = bool
  default     = true
}

variable "enforce_uniform_bucket_level_access" {
  description = "Enforce uniform bucket-level access on Cloud Storage"
  type        = bool
  default     = true
}

variable "restrict_public_ip_cloudsql" {
  description = "Restrict public IPs on Cloud SQL instances"
  type        = bool
  default     = true
}

variable "disable_sa_key_creation" {
  description = "Disable service account key creation"
  type        = bool
  default     = true
}

variable "disable_sa_key_upload" {
  description = "Disable service account key upload"
  type        = bool
  default     = true
}

variable "require_vpc_flow_logs" {
  description = "Require VPC Flow Logs on all subnets"
  type        = bool
  default     = true
}

variable "restrict_vpc_peering" {
  description = "Restrict VPC peering"
  type        = bool
  default     = false
}

variable "restrict_vpn_peer_ips" {
  description = "Restrict VPN peer IPs"
  type        = bool
  default     = false
}

variable "disable_default_network" {
  description = "Skip default network creation in new projects"
  type        = bool
  default     = true
}

variable "require_shielded_vms" {
  description = "Require Shielded VM features"
  type        = bool
  default     = true
}

variable "restrict_cloud_nat" {
  description = "Restrict Cloud NAT creation"
  type        = bool
  default     = false
}

variable "restrict_lb_creation" {
  description = "Restrict load balancer creation"
  type        = bool
  default     = false
}

variable "restrict_shared_vpc" {
  description = "Restrict shared VPC project associations"
  type        = bool
  default     = false
}

variable "restrict_xpn_project_creation" {
  description = "Restrict cross-project networking project creation"
  type        = bool
  default     = false
}

variable "custom_constraints" {
  description = "Map of custom org policy constraints. Each key is the constraint name, value is an object with action_type, condition, method_types, resource_types, display_name, and description."
  type = map(object({
    action_type    = string
    condition      = string
    method_types   = list(string)
    resource_types = list(string)
    display_name   = string
    description    = string
  }))
  default = {}
}
