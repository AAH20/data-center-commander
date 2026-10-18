# Data Center Custom Rule: Network Isolation
# Ensures proper network segmentation and isolation for data center resources
package custom.aws.network.isolation

import data.lib.result

# Rule: AWS security groups should not allow unrestricted SSH access
deny[res] {
	sg := input.aws.ec2.securitygroup[_]
	rule := sg.ingress[_]
	rule.protocol.value == "tcp"
	rule.from_port.value <= 22
	rule.to_port.value >= 22
	cidr := rule.cidr_blocks[_]
	cidr == "0.0.0.0/0"
	msg := "Security group allows unrestricted SSH access from 0.0.0.0/0. Data center policy requires SSH access to be restricted to bastion hosts or specific CIDR ranges."
	res := result.new(msg, sg)
}

# Rule: AWS security groups should not allow unrestricted RDP access
deny[res] {
	sg := input.aws.ec2.securitygroup[_]
	rule := sg.ingress[_]
	rule.protocol.value == "tcp"
	rule.from_port.value <= 3389
	rule.to_port.value >= 3389
	cidr := rule.cidr_blocks[_]
	cidr == "0.0.0.0/0"
	msg := "Security group allows unrestricted RDP access from 0.0.0.0/0. Data center policy requires RDP access to be restricted to bastion hosts or specific CIDR ranges."
	res := result.new(msg, sg)
}

# Rule: AWS security groups should not allow unrestricted database access
deny[res] {
	sg := input.aws.ec2.securitygroup[_]
	rule := sg.ingress[_]
	rule.protocol.value == "tcp"
	rule.from_port.value <= 3306
	rule.to_port.value >= 3306
	cidr := rule.cidr_blocks[_]
	cidr == "0.0.0.0/0"
	msg := "Security group allows unrestricted MySQL access from 0.0.0.0/0. Data center policy requires database access to be restricted to application subnets."
	res := result.new(msg, sg)
}

# Rule: KVM networks should use private IP ranges
deny[res] {
	network := input.libvirt.network[_]
	addr := network.addresses[_]
	not private_ip_range(addr)
	msg := "KVM network uses non-private IP range. Data center policy requires virtual networks to use RFC 1918 private IP ranges."
	res := result.new(msg, network)
}

private_ip_range(addr) {
	startswith(addr, "10.")
}

private_ip_range(addr) {
	startswith(addr, "172.16.")
}

private_ip_range(addr) {
	startswith(addr, "192.168.")
}
