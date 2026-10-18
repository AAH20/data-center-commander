output "instance_ids" {
  description = "IDs of virtual machines"
  value       = azurerm_linux_virtual_machine.this[*].id
}

output "instance_names" {
  description = "Names of virtual machines"
  value       = azurerm_linux_virtual_machine.this[*].name
}

output "instance_public_ips" {
  description = "Public IPs of VMs"
  value       = var.enable_public_ip ? azurerm_public_ip.vm[*].ip_address : []
}

output "instance_private_ips" {
  description = "Private IPs of VMs"
  value       = azurerm_network_interface.this[*].private_ip_address
}

output "nic_ids" {
  description = "Network interface IDs"
  value       = azurerm_network_interface.this[*].id
}
