# network_segmentation.rego — Network segmentation governance for Data Center Commander
package datacenter.network_segmentation

import data.common

# --- Rule: Production resources must not be in public segments ---
deny contains msg if {
    common.is_production
    common.is_public_segment
    msg := sprintf("CRITICAL: Production resource '%s' must not be in a public network segment", [input.resource_id])
}

# --- Rule: Production resources must be in isolated or restricted segments ---
deny contains msg if {
    common.is_production
    not common.is_isolated_segment
    not common.is_restricted_segment
    msg := sprintf("CRITICAL: Production resource '%s' must be in an isolated or restricted network segment", [input.resource_id])
}

# --- Rule: Sensitive data must not be in public segments ---
deny contains msg if {
    common.is_public_segment
    common.has_data_classification
    input.tags["data_classification"] == "sensitive"
    msg := sprintf("CRITICAL: Resource '%s' with sensitive data must not be in a public network segment", [input.resource_id])
}

# --- Rule: Confidential data must not be in public segments ---
deny contains msg if {
    common.is_public_segment
    common.has_data_classification
    input.tags["data_classification"] == "confidential"
    msg := sprintf("CRITICAL: Resource '%s' with confidential data must not be in a public network segment", [input.resource_id])
}

# --- Rule: Restricted data must not be in public segments ---
deny contains msg if {
    common.is_public_segment
    common.has_data_classification
    input.tags["data_classification"] == "restricted"
    msg := sprintf("CRITICAL: Resource '%s' with restricted data must not be in a public network segment", [input.resource_id])
}

# --- Rule: Isolated resources must not have public access ---
deny contains msg if {
    common.is_isolated_segment
    input.network.public_access == true
    msg := sprintf("CRITICAL: Isolated resource '%s' must not have public access", [input.resource_id])
}

# --- Rule: Restricted resources should not have public access ---
deny contains msg if {
    common.is_restricted_segment
    input.network.public_access == true
    msg := sprintf("HIGH: Restricted resource '%s' should not have public access", [input.resource_id])
}

# --- Rule: Public resources must have a WAF ---
deny contains msg if {
    common.is_public_segment
    input.network.waf_enabled != true
    msg := sprintf("HIGH: Public resource '%s' must have a WAF enabled", [input.resource_id])
}

# --- Rule: Public resources must have DDoS protection ---
deny contains msg if {
    common.is_public_segment
    input.network.ddos_protection != true
    msg := sprintf("HIGH: Public resource '%s' must have DDoS protection enabled", [input.resource_id])
}

# --- Rule: Public resources should have a CDN ---
deny contains msg if {
    common.is_public_segment
    input.network.cdn_enabled != true
    msg := sprintf("MEDIUM: Public resource '%s' should have a CDN enabled", [input.resource_id])
}

# --- Rule: Public resources should have a load balancer ---
deny contains msg if {
    common.is_public_segment
    input.network.load_balancer != true
    msg := sprintf("MEDIUM: Public resource '%s' should have a load balancer", [input.resource_id])
}

# --- Rule: Public resources should have a health check ---
deny contains msg if {
    common.is_public_segment
    input.network.health_check != true
    msg := sprintf("MEDIUM: Public resource '%s' should have a health check configured", [input.resource_id])
}

# --- Rule: Public resources must have SSL/TLS enabled ---
deny contains msg if {
    common.is_public_segment
    input.network.ssl_enabled != true
    msg := sprintf("CRITICAL: Public resource '%s' must have SSL/TLS enabled", [input.resource_id])
}

# --- Rule: Public resources must have a valid SSL/TLS certificate ---
deny contains msg if {
    common.is_public_segment
    input.network.ssl_enabled == true
    input.network.ssl_valid != true
    msg := sprintf("CRITICAL: Public resource '%s' has an invalid SSL/TLS certificate", [input.resource_id])
}

# --- Rule: Public resources must not have expiring SSL/TLS certificates ---
deny contains msg if {
    common.is_public_segment
    input.network.ssl_enabled == true
    input.network.ssl_valid == true
    input.network.ssl_expiry_days <= 30
    msg := sprintf("HIGH: Public resource '%s' has an SSL/TLS certificate expiring in %d days", [input.resource_id, input.network.ssl_expiry_days])
}

# --- Rule: Public resources must not have expired SSL/TLS certificates ---
deny contains msg if {
    common.is_public_segment
    input.network.ssl_enabled == true
    input.network.ssl_valid == true
    input.network.ssl_expiry_days <= 0
    msg := sprintf("CRITICAL: Public resource '%s' has an expired SSL/TLS certificate", [input.resource_id])
}

# --- Rule: Public resources must not have weak SSL/TLS configuration ---
deny contains msg if {
    common.is_public_segment
    input.network.ssl_enabled == true
    input.network.ssl_valid == true
    input.network.ssl_strength == "weak"
    msg := sprintf("HIGH: Public resource '%s' has a weak SSL/TLS configuration", [input.resource_id])
}

# --- Rule: Public resources must not use TLS 1.0 ---
deny contains msg if {
    common.is_public_segment
    input.network.ssl_enabled == true
    input.network.ssl_valid == true
    input.network.ssl_version == "TLSv1.0"
    msg := sprintf("CRITICAL: Public resource '%s' uses outdated TLS 1.0", [input.resource_id])
}

# --- Rule: Public resources should not use TLS 1.1 ---
deny contains msg if {
    common.is_public_segment
    input.network.ssl_enabled == true
    input.network.ssl_valid == true
    input.network.ssl_version == "TLSv1.1"
    msg := sprintf("HIGH: Public resource '%s' uses outdated TLS 1.1", [input.resource_id])
}

# --- Rule: Public resources should use TLS 1.3 ---
deny contains msg if {
    common.is_public_segment
    input.network.ssl_enabled == true
    input.network.ssl_valid == true
    input.network.ssl_version == "TLSv1.2"
    msg := sprintf("MEDIUM: Public resource '%s' should use TLS 1.3 instead of TLS 1.2", [input.resource_id])
}

# --- Rule: Public resources must have a firewall ---
deny contains msg if {
    common.is_public_segment
    input.network.firewall_enabled != true
    msg := sprintf("CRITICAL: Public resource '%s' must have a firewall enabled", [input.resource_id])
}

# --- Rule: Public resources must have intrusion detection ---
deny contains msg if {
    common.is_public_segment
    input.network.ids_enabled != true
    msg := sprintf("HIGH: Public resource '%s' must have intrusion detection enabled", [input.resource_id])
}

# --- Rule: Public resources must have a network ACL ---
deny contains msg if {
    common.is_public_segment
    input.network.nacl_enabled != true
    msg := sprintf("HIGH: Public resource '%s' must have a network ACL configured", [input.resource_id])
}

# --- Rule: Public resources must have a security group ---
deny contains msg if {
    common.is_public_segment
    input.network.security_group != true
    msg := sprintf("CRITICAL: Public resource '%s' must have a security group assigned", [input.resource_id])
}

# --- Rule: Public resources must be in a VPC ---
deny contains msg if {
    common.is_public_segment
    input.network.vpc_enabled != true
    msg := sprintf("CRITICAL: Public resource '%s' must be in a VPC", [input.resource_id])
}

# --- Rule: Public resources should be in a private subnet ---
deny contains msg if {
    common.is_public_segment
    input.network.private_subnet != true
    msg := sprintf("HIGH: Public resource '%s' should be in a private subnet", [input.resource_id])
}

# --- Rule: Public resources must have a route table ---
deny contains msg if {
    common.is_public_segment
    input.network.route_table != true
    msg := sprintf("HIGH: Public resource '%s' must have a route table configured", [input.resource_id])
}

# --- Rule: Public resources must have a network interface ---
deny contains msg if {
    common.is_public_segment
    input.network.network_interface != true
    msg := sprintf("CRITICAL: Public resource '%s' must have a network interface", [input.resource_id])
}

# --- Rule: Public resources must have DNS configured ---
deny contains msg if {
    common.is_public_segment
    input.network.dns_enabled != true
    msg := sprintf("HIGH: Public resource '%s' must have DNS configured", [input.resource_id])
}

# --- Rule: Public resources must have Syslog configured ---
deny contains msg if {
    common.is_public_segment
    input.network.syslog_enabled != true
    msg := sprintf("HIGH: Public resource '%s' must have Syslog configured", [input.resource_id])
}

# --- Rule: Public resources must have NTP configured ---
deny contains msg if {
    common.is_public_segment
    input.network.ntp_enabled != true
    msg := sprintf("MEDIUM: Public resource '%s' should have NTP configured", [input.resource_id])
}

# --- Rule: Inter-segment traffic must be explicitly allowed ---
deny contains msg if {
    input.network.inter_segment_traffic == true
    input.network.explicit_allow != true
    msg := sprintf("HIGH: Resource '%s' allows inter-segment traffic without explicit allow rules", [input.resource_id])
}

# --- Rule: Resources must not allow all inbound traffic ---
deny contains msg if {
    input.network.inbound_traffic == "all"
    msg := sprintf("CRITICAL: Resource '%s' allows all inbound traffic", [input.resource_id])
}

# --- Rule: Resources must not allow all outbound traffic ---
deny contains msg if {
    input.network.outbound_traffic == "all"
    msg := sprintf("HIGH: Resource '%s' allows all outbound traffic", [input.resource_id])
}

# --- Rule: Resources must not allow SSH from anywhere ---
deny contains msg if {
    input.network.ssh_cidr == "0.0.0.0/0"
    msg := sprintf("CRITICAL: Resource '%s' allows SSH from anywhere (0.0.0.0/0)", [input.resource_id])
}

# --- Rule: Resources must not allow RDP from anywhere ---
deny contains msg if {
    input.network.rdp_cidr == "0.0.0.0/0"
    msg := sprintf("CRITICAL: Resource '%s' allows RDP from anywhere (0.0.0.0/0)", [input.resource_id])
}

# --- Rule: Resources must not allow database ports from anywhere ---
deny contains msg if {
    input.network.database_cidr == "0.0.0.0/0"
    msg := sprintf("CRITICAL: Resource '%s' allows database access from anywhere (0.0.0.0/0)", [input.resource_id])
}

# --- Rule: Resources must not allow ICMP from anywhere ---
deny contains msg if {
    input.network.icmp_cidr == "0.0.0.0/0"
    msg := sprintf("MEDIUM: Resource '%s' allows ICMP from anywhere (0.0.0.0/0)", [input.resource_id])
}

# --- Rule: Resources must not allow Telnet ---
deny contains msg if {
    input.network.telnet_enabled == true
    msg := sprintf("CRITICAL: Resource '%s' has Telnet enabled", [input.resource_id])
}

# --- Rule: Resources must not allow FTP ---
deny contains msg if {
    input.network.ftp_enabled == true
    msg := sprintf("HIGH: Resource '%s' has FTP enabled (use SFTP instead)", [input.resource_id])
}

# --- Rule: Resources must not allow SNMP v1 ---
deny contains msg if {
    input.network.snmp_version == "v1"
    msg := sprintf("HIGH: Resource '%s' uses SNMP v1 (use SNMP v3 instead)", [input.resource_id])
}

# --- Rule: Resources must not allow SNMP v2c ---
deny contains msg if {
    input.network.snmp_version == "v2c"
    msg := sprintf("HIGH: Resource '%s' uses SNMP v2c (use SNMP v3 instead)", [input.resource_id])
}

# --- Rule: Resources must not allow HTTP without HTTPS ---
deny contains msg if {
    input.network.http_enabled == true
    input.network.https_enabled != true
    msg := sprintf("CRITICAL: Resource '%s' allows HTTP without HTTPS", [input.resource_id])
}

# --- Rule: Resources must not allow SSLv3 ---
deny contains msg if {
    input.network.sslv3_enabled == true
    msg := sprintf("CRITICAL: Resource '%s' has SSLv3 enabled", [input.resource_id])
}

# --- Rule: Resources must not allow TLS 1.0 ---
deny contains msg if {
    input.network.tls_10_enabled == true
    msg := sprintf("CRITICAL: Resource '%s' has TLS 1.0 enabled", [input.resource_id])
}

# --- Rule: Resources must not allow TLS 1.1 ---
deny contains msg if {
    input.network.tls_11_enabled == true
    msg := sprintf("HIGH: Resource '%s' has TLS 1.1 enabled", [input.resource_id])
}

# --- Rule: Resources must not have open ports ---
deny contains msg if {
    count(input.network.open_ports) > 0
    msg := sprintf("HIGH: Resource '%s' has %d open ports that should be reviewed", [input.resource_id, count(input.network.open_ports)])
}

# --- Rule: Resources must not have unused security groups ---
deny contains msg if {
    input.network.unused_security_groups > 0
    msg := sprintf("MEDIUM: Resource '%s' has %d unused security groups", [input.resource_id, input.network.unused_security_groups])
}

# --- Rule: Resources must not have unused network ACLs ---
deny contains msg if {
    input.network.unused_nacls > 0
    msg := sprintf("MEDIUM: Resource '%s' has %d unused network ACLs", [input.resource_id, input.network.unused_nacls])
}

# --- Rule: Resources must not have unused route tables ---
deny contains msg if {
    input.network.unused_route_tables > 0
    msg := sprintf("MEDIUM: Resource '%s' has %d unused route tables", [input.resource_id, input.network.unused_route_tables])
}

# --- Rule: Resources must not have unused network interfaces ---
deny contains msg if {
    input.network.unused_network_interfaces > 0
    msg := sprintf("MEDIUM: Resource '%s' has %d unused network interfaces", [input.resource_id, input.network.unused_network_interfaces])
}

# --- Rule: Resources must not have unused elastic IPs ---
deny contains msg if {
    input.network.unused_elastic_ips > 0
    msg := sprintf("LOW: Resource '%s' has %d unused elastic IPs", [input.resource_id, input.network.unused_elastic_ips])
}

# --- Rule: Resources must not have unused VPCs ---
deny contains msg if {
    input.network.unused_vpcs > 0
    msg := sprintf("MEDIUM: Resource '%s' has %d unused VPCs", [input.resource_id, input.network.unused_vpcs])
}

# --- Rule: Resources must not have unused subnets ---
deny contains msg if {
    input.network.unused_subnets > 0
    msg := sprintf("MEDIUM: Resource '%s' has %d unused subnets", [input.resource_id, input.network.unused_subnets])
}

# --- Rule: Resources must not have unused internet gateways ---
deny contains msg if {
    input.network.unused_internet_gateways > 0
    msg := sprintf("MEDIUM: Resource '%s' has %d unused internet gateways", [input.resource_id, input.network.unused_internet_gateways])
}

# --- Rule: Resources must not have unused NAT gateways ---
deny contains msg if {
    input.network.unused_nat_gateways > 0
    msg := sprintf("MEDIUM: Resource '%s' has %d unused NAT gateways", [input.resource_id, input.network.unused_nat_gateways])
}

# --- Rule: Resources must not have unused VPN connections ---
deny contains msg if {
    input.network.unused_vpn_connections > 0
    msg := sprintf("MEDIUM: Resource '%s' has %d unused VPN connections", [input.resource_id, input.network.unused_vpn_connections])
}

# --- Rule: Resources must not have unused direct connect ---
deny contains msg if {
    input.network.unused_direct_connect > 0
    msg := sprintf("MEDIUM: Resource '%s' has %d unused direct connect connections", [input.resource_id, input.network.unused_direct_connect])
}

# --- Rule: Resources must not have unused transit gateways ---
deny contains msg if {
    input.network.unused_transit_gateways > 0
    msg := sprintf("MEDIUM: Resource '%s' has %d unused transit gateways", [input.resource_id, input.network.unused_transit_gateways])
}

# --- Rule: Resources must not have unused peering connections ---
deny contains msg if {
    input.network.unused_peering_connections > 0
    msg := sprintf("MEDIUM: Resource '%s' has %d unused peering connections", [input.resource_id, input.network.unused_peering_connections])
}

# --- Rule: Resources must not have unused load balancers ---
deny contains msg if {
    input.network.unused_load_balancers > 0
    msg := sprintf("MEDIUM: Resource '%s' has %d unused load balancers", [input.resource_id, input.network.unused_load_balancers])
}

# --- Rule: Resources must not have unused auto scaling groups ---
deny contains msg if {
    input.network.unused_auto_scaling_groups > 0
    msg := sprintf("MEDIUM: Resource '%s' has %d unused auto scaling groups", [input.resource_id, input.network.unused_auto_scaling_groups])
}

# --- Rule: Resources must not have unused launch configurations ---
deny contains msg if {
    input.network.unused_launch_configurations > 0
    msg := sprintf("MEDIUM: Resource '%s' has %d unused launch configurations", [input.resource_id, input.network.unused_launch_configurations])
}

# --- Rule: Resources must not have unused launch templates ---
deny contains msg if {
    input.network.unused_launch_templates > 0
    msg := sprintf("MEDIUM: Resource '%s' has %d unused launch templates", [input.resource_id, input.network.unused_launch_templates])
}

# --- Rule: Resources must not have unused EBS volumes ---
deny contains msg if {
    input.network.unused_ebs_volumes > 0
    msg := sprintf("MEDIUM: Resource '%s' has %d unused EBS volumes", [input.resource_id, input.network.unused_ebs_volumes])
}

# --- Rule: Resources must not have unused EBS snapshots ---
deny contains msg if {
    input.network.unused_ebs_snapshots > 0
    msg := sprintf("LOW: Resource '%s' has %d unused EBS snapshots", [input.resource_id, input.network.unused_ebs_snapshots])
}

# --- Rule: Resources must not have unused AMIs ---
deny contains msg if {
    input.network.unused_amis > 0
    msg := sprintf("LOW: Resource '%s' has %d unused AMIs", [input.resource_id, input.network.unused_amis])
}
