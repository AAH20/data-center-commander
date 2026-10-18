# Data Center Custom Rule: VPC DNS Settings
# Ensures VPC DNS support and hostnames are enabled for internal service discovery
package custom.aws.vpc.dns

import data.lib.result

# Rule: VPC must have DNS support enabled
deny[res] {
	vpc := input.aws.vpc[_]
	vpc.enable_dns_support.value == false
	msg := "VPC does not have DNS support enabled. Data center policy requires DNS support for internal service discovery."
	res := result.new(msg, vpc)
}

# Rule: VPC must have DNS hostnames enabled
deny[res] {
	vpc := input.aws.vpc[_]
	vpc.enable_dns_hostnames.value == false
	msg := "VPC does not have DNS hostnames enabled. Data center policy requires DNS hostnames for internal service discovery."
	res := result.new(msg, vpc)
}
