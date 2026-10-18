# OPA/Rego Policy: AWS IAM Compliance
# Ensures IAM policies follow least privilege and security best practices
package dcc.aws.iam

import future.keywords.if
import future.keywords.in

# Deny IAM policies with wildcard permissions
deny contains msg if {
    some policy in input.aws.iam.policies
    some statement in policy.statements
    statement.effect == "Allow"
    "*" in statement.actions
    msg := sprintf("IAM policy '%s' contains wildcard permissions", [policy.name])
}

# Deny IAM users without MFA
deny contains msg if {
    some user in input.aws.iam.users
    not user.mfa_enabled
    msg := sprintf("IAM user '%s' does not have MFA enabled", [user.name])
}

# Deny access keys older than 90 days
deny contains msg if {
    some key in input.aws.iam.access_keys
    key.age_days > 90
    msg := sprintf("Access key '%s' is older than 90 days", [key.id])
}
