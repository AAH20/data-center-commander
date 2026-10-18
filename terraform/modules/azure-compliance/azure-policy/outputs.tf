output "storage_encryption_assignment_id" {
  description = "ID of the storage encryption policy assignment"
  value       = azurerm_subscription_policy_assignment.storage_encryption.id
}

output "sql_tde_assignment_id" {
  description = "ID of the SQL TDE policy assignment"
  value       = azurerm_subscription_policy_assignment.sql_tde.id
}

output "https_only_assignment_id" {
  description = "ID of the HTTPS-only policy assignment"
  value       = azurerm_subscription_policy_assignment.https_only.id
}

output "keyvault_soft_delete_assignment_id" {
  description = "ID of the Key Vault soft delete policy assignment"
  value       = azurerm_subscription_policy_assignment.keyvault_soft_delete.id
}

output "vm_disk_encryption_assignment_id" {
  description = "ID of the VM disk encryption policy assignment"
  value       = azurerm_subscription_policy_assignment.vm_disk_encryption.id
}

output "nsg_flow_logs_assignment_id" {
  description = "ID of the NSG flow logs policy assignment"
  value       = azurerm_subscription_policy_assignment.nsg_flow_logs.id
}

output "azure_backup_assignment_id" {
  description = "ID of the Azure Backup policy assignment"
  value       = azurerm_subscription_policy_assignment.azure_backup.id
}

output "monitor_diagnostics_assignment_id" {
  description = "ID of the monitor diagnostics policy assignment"
  value       = azurerm_subscription_policy_assignment.monitor_diagnostics.id
}
