# tfsec policy: AWS network security compliance
package custom.aws.network

import data.lib.result

# Deny security groups with unrestricted access
deny[res] {
	sg := input.aws.ec2.security_group[_]
	some rule in sg.ingress
	rule.cidr_blocks[_] == "0.0.0.0/0"
	msg := "Security group allows unrestricted inbound access"
	res := result.new(msg, sg)
}

# Deny VPCs without flow logs
deny[res] {
	vpc := input.aws.vpc[_]
	not vpc.flow_logs_enabled
	msg := "VPC does not have flow logs enabled"
	res := result.new(msg, vpc)
}
