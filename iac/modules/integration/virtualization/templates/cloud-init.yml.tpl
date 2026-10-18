#cloud-config
hostname: ${hostname}
manage_etc_hosts: true
users:
  - name: dc-admin
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - ${ssh_key}
package_update: true
packages:
  - qemu-guest-agent
  - net-tools
  - htop
runcmd:
  - systemctl enable --now qemu-guest-agent
  - echo "Environment: ${environment}" > /etc/dc-environment
