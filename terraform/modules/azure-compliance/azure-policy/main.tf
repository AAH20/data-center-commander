terraform {
  required_version = ">= 1.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.0"
    }
  }
}

data "azurerm_subscription" "current" {}

# Azure Policy: Storage Account Encryption
resource "azurerm_subscription_policy_assignment" "storage_encryption" {
  name                 = "storage-encryption-policy"
  policy_definition_id = "/providers/Microsoft.Authorization/policyDefinitions/6fac406b-40ca-413b-bf8e-0523d61fcdb4"
  subscription_id      = data.azurerm_subscription.current.id
  description          = "Ensure all storage accounts have encryption at rest enabled"
  display_name         = "Storage accounts should have encryption enabled"
  location             = var.location

  identity {
    type = "SystemAssigned"
  }
}

# Azure Policy: SQL Database TDE
resource "azurerm_subscription_policy_assignment" "sql_tde" {
  name                 = "sql-tde-policy"
  policy_definition_id = "/providers/Microsoft.Authorization/policyDefinitions/86a912f6-9a06-4e26-b4cb-5d3417617a5a"
  subscription_id      = data.azurerm_subscription.current.id
  description          = "Ensure all SQL databases have TDE enabled"
  display_name         = "SQL databases should have TDE enabled"
  location             = var.location

  identity {
    type = "SystemAssigned"
  }
}

# Azure Policy: HTTPS Only Storage
resource "azurerm_subscription_policy_assignment" "https_only" {
  name                 = "https-only-policy"
  policy_definition_id = "/providers/Microsoft.Authorization/policyDefinitions/404c3081-a854-4457-ae30-26a93ef604f3"
  subscription_id      = data.azurerm_subscription.current.id
  description          = "Ensure all storage accounts enforce HTTPS-only traffic"
  display_name         = "Storage accounts should enforce HTTPS-only traffic"
  location             = var.location

  identity {
    type = "SystemAssigned"
  }
}

# Azure Policy: Key Vault Soft Delete
resource "azurerm_subscription_policy_assignment" "keyvault_soft_delete" {
  name                 = "keyvault-soft-delete-policy"
  policy_definition_id = "/providers/Microsoft.Authorization/policyDefinitions/1e66c121-a66a-4b1f-9b83-0f31c9fdedcb"
  subscription_id      = data.azurerm_subscription.current.id
  description          = "Ensure all Key Vaults have soft delete enabled"
  display_name         = "Key Vaults should have soft delete enabled"
  location             = var.location

  identity {
    type = "SystemAssigned"
  }
}

# Azure Policy: VM Disk Encryption
resource "azurerm_subscription_policy_assignment" "vm_disk_encryption" {
  name                 = "vm-disk-encryption-policy"
  policy_definition_id = "/providers/Microsoft.Authorization/policyDefinitions/0961003e-5a0a-4549-abde-af6a37f2724d"
  subscription_id      = data.azurerm_subscription.current.id
  description          = "Ensure all VMs have disk encryption enabled"
  display_name         = "Virtual machines should have disk encryption enabled"
  location             = var.location

  identity {
    type = "SystemAssigned"
  }
}

# Azure Policy: NSG Flow Logs
resource "azurerm_subscription_policy_assignment" "nsg_flow_logs" {
  name                 = "nsg-flow-logs-policy"
  policy_definition_id = "/providers/Microsoft.Authorization/policyDefinitions/564feb30-bf6a-4854-b4bb-0d2d2d1e6c66"
  subscription_id      = data.azurerm_subscription.current.id
  description          = "Ensure NSGs have flow logs enabled"
  display_name         = "Network security groups should have flow logs enabled"
  location             = var.location

  identity {
    type = "SystemAssigned"
  }
}

# Azure Policy: Azure Backup
resource "azurerm_subscription_policy_assignment" "azure_backup" {
  name                 = "azure-backup-policy"
  policy_definition_id = "/providers/Microsoft.Authorization/policyDefinitions/013e242c-8828-4970-87b3-ab2475357436"
  subscription_id      = data.azurerm_subscription.current.id
  description          = "Ensure all VMs have Azure Backup enabled"
  display_name         = "Virtual machines should have Azure Backup enabled"
  location             = var.location

  identity {
    type = "SystemAssigned"
  }
}

# Azure Policy: Monitor Diagnostics
resource "azurerm_subscription_policy_assignment" "monitor_diagnostics" {
  name                 = "monitor-diagnostics-policy"
  policy_definition_id = "/providers/Microsoft.Authorization/policyDefinitions/7f89b1eb-583c-429a-8828-af049802c1d9"
  subscription_id      = data.azurerm_subscription.current.id
  description          = "Ensure diagnostic settings are configured for all resources"
  display_name         = "Diagnostic settings should be configured for all resources"
  location             = var.location

  identity {
    type = "SystemAssigned"
  }
}
