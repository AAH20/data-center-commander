terraform {
  required_version = ">= 1.5.0"
  required_providers {
    openshift = {
      source  = "openshift/openshift"
      version = "~> 1.0"
    }
  }
}

# Provision an OpenShift cluster using openshift-install.
# This module wraps the openshift-install binary invocation via a
# null_resource + local-exec provisioner. For managed OpenShift
# (ARO, ROSA, OSD), use the respective cloud provider modules instead.
#
# Prerequisites:
#   - openshift-install binary in PATH
#   - Pull secret and SSH key configured in variables
#   - Cloud credentials in environment (AWS_PROFILE, AZURE_CREDENTIALS, etc.)

resource "null_resource" "openshift_cluster" {
  triggers = {
    # Re-run install when these change
    cluster_name   = var.cluster_name
    base_domain    = var.base_domain
    cloud_provider = var.cloud_provider
    region         = var.region
    version        = var.openshift_version
    pull_secret    = md5(var.pull_secret)
    ssh_public_key = md5(var.ssh_public_key)
  }

  provisioner "local-exec" {
    command = <<-EOT
      openshift-install create cluster \
        --dir=${path.module}/.install-dir \
        --log-level=info \
        --cluster-name=${var.cluster_name} \
        --base-domain=${var.base_domain} \
        --cloud=${var.cloud_provider} \
        --region=${var.region} \
        --version=${var.openshift_version} \
        --pull-secret='${var.pull_secret}' \
        --ssh-public-key='${var.ssh_public_key}' \
        ${var.additional_install_flags}
    EOT
  }

  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
      openshift-install destroy cluster \
        --dir=${path.module}/.install-dir \
        --log-level=info
    EOT
  }
}
