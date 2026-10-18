variable "project_name" {
  description = "Project name"
  type        = string
}

variable "enable_aws" {
  description = "Enable AWS IAM"
  type        = bool
  default     = false
}

variable "enable_gcp" {
  description = "Enable GCP IAM"
  type        = bool
  default     = false
}

variable "enable_azure" {
  description = "Enable Azure RBAC"
  type        = bool
  default     = false
}

variable "enable_ibm" {
  description = "Enable IBM Cloud IAM"
  type        = bool
  default     = false
}

variable "gcp_project_id" {
  description = "GCP project ID"
  type        = string
  default     = ""
}

variable "gcp_workload_roles" {
  description = "GCP IAM roles for workload service account"
  type        = list(string)
  default = [
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/storage.objectViewer"
  ]
}

variable "azure_subscription_id" {
  description = "Azure subscription ID"
  type        = string
  default     = ""
}

variable "common_tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
