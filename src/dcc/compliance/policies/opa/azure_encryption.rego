# OPA/Rego Policy: Azure Encryption Compliance
# Ensures Azure resources have encryption enabled
package dcc.azure.encryption

import future.keywords.if
import future.keywords.in

# Deny storage accounts without encryption
deny contains msg if {
    some account in input.azure.storage.accounts
    not account.encryption_enabled
    msg := sprintf("Storage account '%s' does not have encryption enabled", [account.name])
}

# Deny SQL databases without TDE
deny contains msg if {
    some db in input.azure.sql.databases
    not db.tde_enabled
    msg := sprintf("SQL database '%s' does not have TDE enabled", [db.name])
}

# Deny VMs without disk encryption
deny contains msg if {
    some vm in input.azure.compute.virtual_machines
    not vm.disk_encryption_enabled
    msg := sprintf("Virtual machine '%s' does not have disk encryption enabled", [vm.name])
}
