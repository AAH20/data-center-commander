# Data Center Custom Rule: Default Security Group
# Ensures default security groups have no ingress/egress rules
package custom.aws.vpc.default_sg

import data.lib.result

# Rule: Default security groups should not have ingress rules
deny[res] {
	sg := input.aws.vpc.defaultsecuritygroup[_]
	sg.ingress
	msg := "Default security group has ingress rules. Data center policy requires default security groups to have no inbound rules."
	res := result.new(msg, sg)
}

# Rule: Default security groups should not have egress rules
deny[res] {
	sg := input.aws.vpc.defaultsecuritygroup[_]
	sg.egress
	msg := "Default security group has egress rules. Data center policy requires default security groups to have no outbound rules."
	res := result.new(msg, sg)
}

# Rule: Default security group should be tagged for identification
warn[res] {
	sg := input.aws.vpc.defaultsecuritygroup[_]
	not sg.tags
	msg := "Default security group is missing tags. Data center policy requires all resources to be tagged for asset management."
	res := result.new(msg, sg)
}
