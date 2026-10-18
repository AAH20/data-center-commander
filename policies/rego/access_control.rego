# access_control.rego — Access control governance for Data Center Commander
package datacenter.access_control

import data.common

# --- Rule: Production resources must have MFA enabled ---
deny contains msg if {
    common.is_production
    not common.mfa_enabled
    msg := sprintf("CRITICAL: Production resource '%s' must have MFA enabled", [input.resource_id])
}

# --- Rule: Staging resources must have MFA enabled ---
deny contains msg if {
    common.is_staging
    not common.mfa_enabled
    msg := sprintf("HIGH: Staging resource '%s' must have MFA enabled", [input.resource_id])
}

# --- Rule: Resources must use least privilege access ---
deny contains msg if {
    not common.least_privilege
    msg := sprintf("HIGH: Resource '%s' must use least privilege access", [input.resource_id])
}

# --- Rule: Production resources must not have admin access ---
deny contains msg if {
    common.is_production
    input.access.role == "admin"
    msg := sprintf("CRITICAL: Production resource '%s' must not have admin access", [input.resource_id])
}

# --- Rule: Production resources must not have root access ---
deny contains msg if {
    common.is_production
    input.access.role == "root"
    msg := sprintf("CRITICAL: Production resource '%s' must not have root access", [input.resource_id])
}

# --- Rule: Production resources must not have superuser access ---
deny contains msg if {
    common.is_production
    input.access.role == "superuser"
    msg := sprintf("CRITICAL: Production resource '%s' must not have superuser access", [input.resource_id])
}

# --- Rule: Production resources must not have owner access ---
deny contains msg if {
    common.is_production
    input.access.role == "owner"
    msg := sprintf("CRITICAL: Production resource '%s' must not have owner access", [input.resource_id])
}

# --- Rule: Production resources must not have full access ---
deny contains msg if {
    common.is_production
    input.access.role == "full"
    msg := sprintf("CRITICAL: Production resource '%s' must not have full access", [input.resource_id])
}

# --- Rule: Production resources should not have write access ---
deny contains msg if {
    common.is_production
    input.access.role == "write"
    msg := sprintf("HIGH: Production resource '%s' should not have write access", [input.resource_id])
}

# --- Rule: Production resources should not have read-write access ---
deny contains msg if {
    common.is_production
    input.access.role == "read-write"
    msg := sprintf("HIGH: Production resource '%s' should not have read-write access", [input.resource_id])
}

# --- Rule: Production resources should not have read-only access ---
deny contains msg if {
    common.is_production
    input.access.role == "read-only"
    msg := sprintf("MEDIUM: Production resource '%s' should not have read-only access", [input.resource_id])
}

# --- Rule: Production resources should not have read access ---
deny contains msg if {
    common.is_production
    input.access.role == "read"
    msg := sprintf("MEDIUM: Production resource '%s' should not have read access", [input.resource_id])
}

# --- Rule: Production resources must not have custom access ---
deny contains msg if {
    common.is_production
    input.access.role == "custom"
    msg := sprintf("MEDIUM: Production resource '%s' has custom access which should be reviewed", [input.resource_id])
}

# --- Rule: Production resources must not have default access ---
deny contains msg if {
    common.is_production
    input.access.role == "default"
    msg := sprintf("HIGH: Production resource '%s' has default access which should be changed", [input.resource_id])
}

# --- Rule: Production resources must not have guest access ---
deny contains msg if {
    common.is_production
    input.access.role == "guest"
    msg := sprintf("CRITICAL: Production resource '%s' has guest access", [input.resource_id])
}

# --- Rule: Production resources must not have anonymous access ---
deny contains msg if {
    common.is_production
    input.access.role == "anonymous"
    msg := sprintf("CRITICAL: Production resource '%s' has anonymous access", [input.resource_id])
}

# --- Rule: Production resources must not have public access ---
deny contains msg if {
    common.is_production
    input.access.role == "public"
    msg := sprintf("CRITICAL: Production resource '%s' has public access", [input.resource_id])
}

# --- Rule: Production resources must not have external access ---
deny contains msg if {
    common.is_production
    input.access.role == "external"
    msg := sprintf("HIGH: Production resource '%s' has external access", [input.resource_id])
}

# --- Rule: Production resources must not have partner access ---
deny contains msg if {
    common.is_production
    input.access.role == "partner"
    msg := sprintf("HIGH: Production resource '%s' has partner access", [input.resource_id])
}

# --- Rule: Production resources must not have vendor access ---
deny contains msg if {
    common.is_production
    input.access.role == "vendor"
    msg := sprintf("HIGH: Production resource '%s' has vendor access", [input.resource_id])
}

# --- Rule: Production resources must not have contractor access ---
deny contains msg if {
    common.is_production
    input.access.role == "contractor"
    msg := sprintf("HIGH: Production resource '%s' has contractor access", [input.resource_id])
}

# --- Rule: Production resources must not have temp access ---
deny contains msg if {
    common.is_production
    input.access.role == "temp"
    msg := sprintf("HIGH: Production resource '%s' has temp access", [input.resource_id])
}

# --- Rule: Production resources must not have service account access ---
deny contains msg if {
    common.is_production
    input.access.role == "service-account"
    msg := sprintf("MEDIUM: Production resource '%s' has service account access", [input.resource_id])
}

# --- Rule: Production resources must not have API access ---
deny contains msg if {
    common.is_production
    input.access.role == "api"
    msg := sprintf("MEDIUM: Production resource '%s' has API access", [input.resource_id])
}

# --- Rule: Production resources must not have webhook access ---
deny contains msg if {
    common.is_production
    input.access.role == "webhook"
    msg := sprintf("MEDIUM: Production resource '%s' has webhook access", [input.resource_id])
}

# --- Rule: Production resources must not have callback access ---
deny contains msg if {
    common.is_production
    input.access.role == "callback"
    msg := sprintf("MEDIUM: Production resource '%s' has callback access", [input.resource_id])
}

# --- Rule: Production resources must not have redirect access ---
deny contains msg if {
    common.is_production
    input.access.role == "redirect"
    msg := sprintf("MEDIUM: Production resource '%s' has redirect access", [input.resource_id])
}

# --- Rule: Production resources must not have proxy access ---
deny contains msg if {
    common.is_production
    input.access.role == "proxy"
    msg := sprintf("MEDIUM: Production resource '%s' has proxy access", [input.resource_id])
}

# --- Rule: Production resources must not have tunnel access ---
deny contains msg if {
    common.is_production
    input.access.role == "tunnel"
    msg := sprintf("MEDIUM: Production resource '%s' has tunnel access", [input.resource_id])
}

# --- Rule: Production resources must not have VPN access ---
deny contains msg if {
    common.is_production
    input.access.role == "vpn"
    msg := sprintf("MEDIUM: Production resource '%s' has VPN access", [input.resource_id])
}

# --- Rule: Production resources must not have SSH access ---
deny contains msg if {
    common.is_production
    input.access.role == "ssh"
    msg := sprintf("MEDIUM: Production resource '%s' has SSH access", [input.resource_id])
}

# --- Rule: Production resources must not have RDP access ---
deny contains msg if {
    common.is_production
    input.access.role == "rdp"
    msg := sprintf("MEDIUM: Production resource '%s' has RDP access", [input.resource_id])
}

# --- Rule: Production resources must not have FTP access ---
deny contains msg if {
    common.is_production
    input.access.role == "ftp"
    msg := sprintf("MEDIUM: Production resource '%s' has FTP access", [input.resource_id])
}

# --- Rule: Production resources must not have SFTP access ---
deny contains msg if {
    common.is_production
    input.access.role == "sftp"
    msg := sprintf("MEDIUM: Production resource '%s' has SFTP access", [input.resource_id])
}

# --- Rule: Production resources must not have SCP access ---
deny contains msg if {
    common.is_production
    input.access.role == "scp"
    msg := sprintf("MEDIUM: Production resource '%s' has SCP access", [input.resource_id])
}

# --- Rule: Production resources must not have TFTP access ---
deny contains msg if {
    common.is_production
    input.access.role == "tftp"
    msg := sprintf("MEDIUM: Production resource '%s' has TFTP access", [input.resource_id])
}

# --- Rule: Production resources must not have Telnet access ---
deny contains msg if {
    common.is_production
    input.access.role == "telnet"
    msg := sprintf("CRITICAL: Production resource '%s' has Telnet access", [input.resource_id])
}

# --- Rule: Production resources must not have SNMP access ---
deny contains msg if {
    common.is_production
    input.access.role == "snmp"
    msg := sprintf("MEDIUM: Production resource '%s' has SNMP access", [input.resource_id])
}

# --- Rule: Production resources must not have ICMP access ---
deny contains msg if {
    common.is_production
    input.access.role == "icmp"
    msg := sprintf("MEDIUM: Production resource '%s' has ICMP access", [input.resource_id])
}

# --- Rule: Production resources must not have DNS access ---
deny contains msg if {
    common.is_production
    input.access.role == "dns"
    msg := sprintf("MEDIUM: Production resource '%s' has DNS access", [input.resource_id])
}

# --- Rule: Production resources must not have DHCP access ---
deny contains msg if {
    common.is_production
    input.access.role == "dhcp"
    msg := sprintf("MEDIUM: Production resource '%s' has DHCP access", [input.resource_id])
}

# --- Rule: Production resources must not have NTP access ---
deny contains msg if {
    common.is_production
    input.access.role == "ntp"
    msg := sprintf("MEDIUM: Production resource '%s' has NTP access", [input.resource_id])
}

# --- Rule: Production resources must not have Syslog access ---
deny contains msg if {
    common.is_production
    input.access.role == "syslog"
    msg := sprintf("MEDIUM: Production resource '%s' has Syslog access", [input.resource_id])
}

# --- Rule: Production resources must not have NetFlow access ---
deny contains msg if {
    common.is_production
    input.access.role == "netflow"
    msg := sprintf("MEDIUM: Production resource '%s' has NetFlow access", [input.resource_id])
}

# --- Rule: Production resources must not have sFlow access ---
deny contains msg if {
    common.is_production
    input.access.role == "sflow"
    msg := sprintf("MEDIUM: Production resource '%s' has sFlow access", [input.resource_id])
}

# --- Rule: Production resources must not have IPFIX access ---
deny contains msg if {
    common.is_production
    input.access.role == "ipfix"
    msg := sprintf("MEDIUM: Production resource '%s' has IPFIX access", [input.resource_id])
}

# --- Rule: Production resources must not have GRE tunnel access ---
deny contains msg if {
    common.is_production
    input.access.role == "gre-tunnel"
    msg := sprintf("MEDIUM: Production resource '%s' has GRE tunnel access", [input.resource_id])
}

# --- Rule: Production resources must not have IPsec tunnel access ---
deny contains msg if {
    common.is_production
    input.access.role == "ipsec-tunnel"
    msg := sprintf("MEDIUM: Production resource '%s' has IPsec tunnel access", [input.resource_id])
}

# --- Rule: Production resources must not have VXLAN access ---
deny contains msg if {
    common.is_production
    input.access.role == "vxlan"
    msg := sprintf("MEDIUM: Production resource '%s' has VXLAN access", [input.resource_id])
}

# --- Rule: Production resources must not have Geneve access ---
deny contains msg if {
    common.is_production
    input.access.role == "geneve"
    msg := sprintf("MEDIUM: Production resource '%s' has Geneve access", [input.resource_id])
}

# --- Rule: Production resources must not have STT access ---
deny contains msg if {
    common.is_production
    input.access.role == "stt"
    msg := sprintf("MEDIUM: Production resource '%s' has STT access", [input.resource_id])
}

# --- Rule: Production resources must not have NVGRE access ---
deny contains msg if {
    common.is_production
    input.access.role == "nvgre"
    msg := sprintf("MEDIUM: Production resource '%s' has NVGRE access", [input.resource_id])
}

# --- Rule: Production resources must not have MPLS access ---
deny contains msg if {
    common.is_production
    input.access.role == "mpls"
    msg := sprintf("MEDIUM: Production resource '%s' has MPLS access", [input.resource_id])
}

# --- Rule: Production resources must not have SD-WAN access ---
deny contains msg if {
    common.is_production
    input.access.role == "sd-wan"
    msg := sprintf("MEDIUM: Production resource '%s' has SD-WAN access", [input.resource_id])
}
