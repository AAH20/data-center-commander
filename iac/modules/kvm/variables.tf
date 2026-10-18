variable "libvirt_uri" {
  description = "Libvirt connection URI (e.g. qemu:///system, qemu+ssh://user@host/system)"
  type        = string
  default     = "qemu:///system"
}

variable "storage_pool_name" {
  description = "Name of the storage pool"
  type        = string
  default     = "default"
}

variable "storage_pool_path" {
  description = "Filesystem path for the storage pool"
  type        = string
  default     = "/var/lib/libvirt/images"
}

variable "networks" {
  description = "List of virtual networks to create"
  type = list(object({
    name         = string
    mode         = optional(string, "nat")
    domain       = optional(string)
    addresses    = list(string)
    dns_enabled  = optional(bool, true)
    dhcp_enabled = optional(bool, true)
    autostart    = optional(bool, true)
  }))
  default = []
}

variable "vm_name" {
  description = "Name of the virtual machine"
  type        = string
}

variable "vm_memory" {
  description = "Memory in MiB"
  type        = number
  default     = 2048
}

variable "vm_vcpu" {
  description = "Number of virtual CPUs"
  type        = number
  default     = 2
}

variable "vm_disk_size" {
  description = "Root disk size in GB"
  type        = number
  default     = 20
}

variable "vm_os_variant" {
  description = "OS variant for optimisation (e.g. ubuntu22.04, centos-stream9)"
  type        = string
  default     = "ubuntu22.04"
}

variable "vm_network_interfaces" {
  description = "List of network interfaces to attach"
  type = list(object({
    network_name = string
    mac          = optional(string)
    addresses    = optional(list(string))
    hostname     = optional(string)
  }))
  default = []
}

variable "vm_cloud_init" {
  description = "Cloud-init configuration (user-data YAML)"
  type        = string
  default     = ""
}

variable "vm_ssh_keys" {
  description = "List of SSH public keys to inject via cloud-init"
  type        = list(string)
  default     = []
}

variable "vm_base_volume_name" {
  description = "Base volume name to clone from (cloud image)"
  type        = string
}

variable "vm_storage_pool" {
  description = "Storage pool for the VM disk"
  type        = string
  default     = "default"
}

variable "vm_extra_volumes" {
  description = "Additional volumes to attach"
  type = list(object({
    name   = string
    size_gb = number
    pool   = optional(string)
    format = optional(string)
  }))
  default = []
}

variable "vm_autostart" {
  description = "Autostart VM when libvirt starts"
  type        = bool
  default     = true
}

variable "vm_tags" {
  description = "Tags to apply to the VM"
  type        = map(string)
  default     = {}
}
