# tfsec policy: Azure encryption compliance
package custom.azure.encryption

import data.lib.result

# Deny storage accounts without encryption
deny[res] {
	account := input.azure.storage.account[_]
	not account.encryption_enabled
	msg := "Storage account does not have encryption enabled"
	res := result.new(msg, account)
}

# Deny SQL databases without TDE
deny[res] {
	db := input.azure.sql.database[_]
	not db.tde_enabled
	msg := "SQL database does not have TDE enabled"
	res := result.new(msg, db)
}
