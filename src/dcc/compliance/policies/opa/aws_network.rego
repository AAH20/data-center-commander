# OPA/Rego Policy: AWS Network Security Compliance
# Ensures network security best practices for AWS resources
package dcc.aws.network

import future.keywords.if
import future.keywords.in

# Deny security groups with unrestricted inbound access
deny contains msg if {
    some sg in input.aws.ec2.security_groups
    some rule in sg.ip_permissions
    some cidr in rule.ip_ranges
    cidr.cidr_ip == "0.0.0.0/0"
    msg := sprintf("Security group '%s' allows unrestricted inbound access (0.0.0.0/0)", [sg.id])
}

# Deny VPCs without flow logs
deny contains msg if {
    some vpc in input.aws.vpc.vpcs
    not vpc.flow_logs_enabled
    msg := sprintf("VPC '%s' does not have flow logs enabled", [vpc.id])
}

# Deny public subnets with auto-assign public IP
deny contains msg if {
    some subnet in input.aws.vpc.subnets
    subnet.map_public_ip_on_launch == true
    msg := sprintf("Subnet '%s' auto-assigns public IP addresses", [subnet.id])
}
