output "vm_id" {
  description = "ID of the created VM"
  value       = libvirt_domain.vm.id
}

output "vm_name" {
  description = "Name of the VM"
  value       = var.vm_name
}

output "vm_memory" {
  description = "Memory allocated to the VM (MiB)"
  value       = var.vm_memory
}

output "vm_vcpu" {
  description = "Number of vCPUs"
  value       = var.vm_vcpu
}

output "vm_network_interfaces" {
  description = "Network interfaces attached to the VM"
  value       = var.vm_network_interfaces
}

output "vm_ip_addresses" {
  description = "IP addresses assigned to the VM (populated after boot)"
  value       = try(libvirt_domain.vm.network_interface.*.addresses, [])
}
