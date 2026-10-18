output "pool_name" {
  description = "Name of the libvirt storage pool"
  value       = libvirt_pool.data_center.name
}

output "network_id" {
  description = "ID of the virtual network"
  value       = libvirt_network.data_center.id
}

output "network_name" {
  description = "Name of the virtual network"
  value       = libvirt_network.data_center.name
}

output "vm_names" {
  description = "Names of all provisioned VMs"
  value       = libvirt_domain.vm[*].name
}

output "vm_ips" {
  description = "IP addresses of all provisioned VMs"
  value       = libvirt_domain.vm[*].network_interface[0].addresses
}

output "vm_ids" {
  description = "Libvirt domain IDs of all VMs"
  value       = libvirt_domain.vm[*].id
}

output "base_volume_id" {
  description = "ID of the base volume"
  value       = libvirt_volume.base.id
}
