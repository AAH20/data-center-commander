# Data Center Custom Rule: Resource Tagging
# Ensures all data center resources have required tags for asset management
package custom.aws.tagging

import data.lib.result

# Required tags for data center resources
required_tags := {"Name", "Environment", "Owner", "DataCenter"}

# Rule: AWS VPC must have all required tags
deny[res] {
	vpc := input.aws.vpc[_]
	missing := required_tags - object.keys(vpc.tags)
	count(missing) > 0
	msg := sprintf("VPC is missing required tags: %v. Data center policy requires all resources to have Name, Environment, Owner, and DataCenter tags.", [missing])
	res := result.new(msg, vpc)
}

# Rule: AWS security groups must have all required tags
deny[res] {
	sg := input.aws.ec2.securitygroup[_]
	missing := required_tags - object.keys(sg.tags)
	count(missing) > 0
	msg := sprintf("Security group is missing required tags: %v. Data center policy requires all resources to have Name, Environment, Owner, and DataCenter tags.", [missing])
	res := result.new(msg, sg)
}

# Rule: AWS config resources must have all required tags
deny[res] {
	rule := input.aws.config.configrule[_]
	missing := required_tags - object.keys(rule.tags)
	count(missing) > 0
	msg := sprintf("AWS Config rule is missing required tags: %v. Data center policy requires all resources to have Name, Environment, Owner, and DataCenter tags.", [missing])
	res := result.new(msg, rule)
}

# Rule: libvirt resources should have tags
warn[res] {
	domain := input.libvirt.domain[_]
	not domain.tags
	msg := "libvirt domain is missing tags. Data center policy requires all resources to be tagged for asset management."
	res := result.new(msg, domain)
}
