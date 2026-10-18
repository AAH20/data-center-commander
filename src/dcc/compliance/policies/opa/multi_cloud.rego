# OPA/Rego Policy: Multi-Cloud Compliance
# Cross-cloud compliance policies applicable to all providers
package dcc.multi_cloud

import future.keywords.if
import future.keywords.in

# Deny any resource without tags/labels
deny contains msg if {
    some resource in input.resources
    not resource.tags
    msg := sprintf("Resource '%s' does not have tags", [resource.id])
}

# Deny any resource without encryption
deny contains msg if {
    some resource in input.resources
    resource.type in ["storage", "database", "volume"]
    not resource.encrypted
    msg := sprintf("Resource '%s' (type: %s) does not have encryption enabled", [resource.id, resource.type])
}

# Deny any resource with public access
deny contains msg if {
    some resource in input.resources
    resource.publicly_accessible == true
    msg := sprintf("Resource '%s' is publicly accessible", [resource.id])
}

# Deny any resource without backup enabled
deny contains msg if {
    some resource in input.resources
    resource.type in ["database", "volume", "instance"]
    not resource.backup_enabled
    msg := sprintf("Resource '%s' (type: %s) does not have backup enabled", [resource.id, resource.type])
}
