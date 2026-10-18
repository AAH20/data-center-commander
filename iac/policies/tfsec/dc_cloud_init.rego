# Data Center Custom Rule: Cloud-Init Security
# Ensures cloud-init configurations follow security best practices
package custom.libvirt.cloudinit

import data.lib.result

# Rule: Cloud-init should not contain plaintext passwords
deny[res] {
	cloudinit := input.libvirt.cloudinitdisk[_]
	contains(lower(cloudinit.user_data.value), "password:")
	msg := "Cloud-init configuration contains plaintext password. Data center policy requires SSH key authentication instead of passwords."
	res := result.new(msg, cloudinit)
}

# Rule: Cloud-init should not disable SSH password authentication warning
warn[res] {
	cloudinit := input.libvirt.cloudinitdisk[_]
	contains(lower(cloudinit.user_data.value), "ssh_pwauth: true")
	msg := "Cloud-init enables SSH password authentication. Data center policy recommends disabling password authentication and using SSH keys only."
	res := result.new(msg, cloudinit)
}

# Rule: Cloud-init should not contain hardcoded API keys or secrets
deny[res] {
	cloudinit := input.libvirt.cloudinitdisk[_]
	contains(lower(cloudinit.user_data.value), "api_key:")
	msg := "Cloud-init configuration contains hardcoded API key. Data center policy requires secrets to be injected via secure vaults."
	res := result.new(msg, cloudinit)
}

# Rule: Cloud-init should not contain hardcoded tokens
deny[res] {
	cloudinit := input.libvirt.cloudinitdisk[_]
	contains(lower(cloudinit.user_data.value), "token:")
	msg := "Cloud-init configuration contains hardcoded token. Data center policy requires secrets to be injected via secure vaults."
	res := result.new(msg, cloudinit)
}
