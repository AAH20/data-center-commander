# OPA/Rego Policy: Azure Network Security Compliance
# Ensures Azure network security best practices
package dcc.azure.network

import future.keywords.if
import future.keywords.in

# Deny NSGs with unrestricted inbound access
deny contains msg if {
    some nsg in input.azure.network.security_groups
    some rule in nsg.security_rules
    rule.direction == "Inbound"
    rule.access == "Allow"
    rule.source_address_prefix == "*"
    msg := sprintf("NSG '%s' allows unrestricted inbound access", [nsg.name])
}

# Deny storage accounts without HTTPS-only
deny contains msg if {
    some account in input.azure.storage.accounts
    not account.https_only
    msg := sprintf("Storage account '%s' does not enforce HTTPS-only traffic", [account.name])
}
