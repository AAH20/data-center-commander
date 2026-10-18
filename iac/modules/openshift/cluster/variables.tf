variable "cluster_name" {
  description = "Name of the OpenShift cluster"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,20}[a-z0-9]$", var.cluster_name))
    error_message = "Cluster name must be 2-22 lowercase alphanumeric characters or hyphens, starting and ending with alphanumeric."
  }
}

variable "base_domain" {
  description = "Base DNS domain for the cluster (e.g. example.com)"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9.-]*\\.[a-z]{2,}$", var.base_domain))
    error_message = "Must be a valid DNS domain."
  }
}

variable "cloud_provider" {
  description = "Cloud provider for the cluster (aws, azure, gcp)"
  type        = string
  default     = "aws"

  validation {
    condition     = contains(["aws", "azure", "gcp"], var.cloud_provider)
    error_message = "Must be aws, azure, or gcp."
  }
}

variable "region" {
  description = "Cloud region for the cluster"
  type        = string
}

variable "openshift_version" {
  description = "OpenShift version to install (e.g. 4.15.0)"
  type        = string
}

variable "pull_secret" {
  description = "OpenShift pull secret (JSON string) from https://console.redhat.com/openshift/install/pull-secret"
  type        = string
  sensitive   = true
}

variable "ssh_public_key" {
  description = "SSH public key for cluster node access"
  type        = string
}

variable "additional_install_flags" {
  description = "Additional flags to pass to openshift-install (e.g. '--compute-nodes=3')"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags to apply to cloud resources"
  type        = map(string)
  default     = {}
}
