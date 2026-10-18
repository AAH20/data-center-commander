# Data Center Custom Rule: IAM Security
# Ensures IAM roles and policies follow least-privilege principles
package custom.aws.iam

import data.lib.result

# Rule: IAM roles should not have wildcard permissions on all resources
deny[res] {
	role := input.aws.iam.role[_]
	policy := role.assume_role_policy[_]
	contains(policy, "*")
	msg := "IAM role assume role policy contains wildcard. Data center policy requires explicit principal specification."
	res := result.new(msg, role)
}

# Rule: IAM policies should not have full admin access
deny[res] {
	policy := input.aws.iam.rolepolicy[_]
	contains(policy.policy, "\"Action\":\"*\"")
	msg := "IAM policy grants full admin access (*). Data center policy requires least-privilege permissions."
	res := result.new(msg, policy)
}

# Rule: IAM policies should not have wildcard resource with sensitive actions
deny[res] {
	policy := input.aws.iam.rolepolicy[_]
	contains(policy.policy, "\"Resource\":\"*\"")
	contains(policy.policy, "iam:")
	msg := "IAM policy allows IAM actions on all resources. Data center policy requires IAM actions to be scoped to specific resources."
	res := result.new(msg, policy)
}

# Rule: IAM roles should have description
warn[res] {
	role := input.aws.iam.role[_]
	not role.description
	msg := "IAM role is missing description. Data center policy requires descriptions for all IAM roles for audit purposes."
	res := result.new(msg, role)
}
