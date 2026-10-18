# Data Center Custom Rule: KVM/libvirt Security
# Ensures KVM virtualization resources follow data center security practices
package custom.libvirt.security

import data.lib.result

# Rule: libvirt provider URI should not use unencrypted remote connections
deny[res] {
	provider := input.libvirt.provider[_]
	provider.uri.value == "qemu+ssh://"
	msg := "libvirt provider uses unencrypted SSH URI. Data center policy requires TLS-encrypted connections (qemu+tls://) for remote libvirt."
	res := result.new(msg, provider)
}

# Rule: libvirt provider should not use system session for untrusted workloads
warn[res] {
	provider := input.libvirt.provider[_]
	provider.uri.value == "qemu:///system"
	msg := "libvirt provider uses system session. Data center policy recommends using polkit-authenticated sessions (qemu:///session) for untrusted workloads."
	res := result.new(msg, provider)
}

# Rule: KVM storage pool path should be under /var/lib/libvirt or /data
deny[res] {
	pool := input.libvirt.pool[_]
	not data_center_path(pool.path.value)
	msg := "KVM storage pool path is outside approved data center paths. Data center policy requires storage under /var/lib/libvirt/ or /data/."
	res := result.new(msg, pool)
}

data_center_path(path) {
	startswith(path, "/var/lib/libvirt/")
}

data_center_path(path) {
	startswith(path, "/data/")
}

# Rule: KVM network should not use isolated mode for production workloads
warn[res] {
	network := input.libvirt.network[_]
	network.mode.value == "isolated"
	msg := "KVM network uses isolated mode. Data center policy recommends NAT or routed mode for production workloads requiring external connectivity."
	res := result.new(msg, network)
}

# Rule: KVM domain should have autostart disabled for non-critical VMs
warn[res] {
	domain := input.libvirt.domain[_]
	domain.autostart.value == true
	msg := "KVM domain has autostart enabled. Data center policy recommends disabling autostart for non-critical VMs to control boot order and resource allocation."
	res := result.new(msg, domain)
}
