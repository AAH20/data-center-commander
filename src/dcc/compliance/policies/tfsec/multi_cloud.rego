# tfsec policy: Multi-cloud compliance
package custom.multi_cloud

import data.lib.result

# Deny any resource without tags
deny[res] {
	resource := input.resources[_]
	not resource.tags
	msg := "Resource does not have tags"
	res := result.new(msg, resource)
}

# Deny storage resources without encryption
deny[res] {
	resource := input.resources[_]
	resource.type in ["storage", "database", "volume"]
	not resource.encrypted
	msg := "Storage resource does not have encryption enabled"
	res := result.new(msg, resource)
}
