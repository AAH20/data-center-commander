variable "organization_id" {
  description = "GCP organization ID (numeric)"
  type        = string

  validation {
    condition     = can(regex("^[0-9]+$", var.organization_id))
    error_message = "Must be a numeric organization ID."
  }
}

variable "create_access_policy" {
  description = "Create a new access policy (set to false to use existing)"
  type        = bool
  default     = true
}

variable "existing_access_policy_id" {
  description = "Existing access policy ID (required if create_access_policy is false)"
  type        = string
  default     = null
}

variable "access_policy_title" {
  description = "Title for the access policy"
  type        = string
  default     = "Data Center Commander Access Policy"
}

variable "create_service_perimeter" {
  description = "Create a service perimeter"
  type        = bool
  default     = true
}

variable "perimeter_name" {
  description = "Name of the service perimeter"
  type        = string
  default     = "datacenter_perimeter"
}

variable "perimeter_resources" {
  description = "List of project IDs to include in the service perimeter (format: projects/PROJECT_NUMBER)"
  type        = list(string)
  default     = []
}

variable "restricted_services" {
  description = "List of service names to restrict within the perimeter"
  type        = list(string)
  default = [
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "compute.googleapis.com",
    "container.googleapis.com",
    "pubsub.googleapis.com",
    "cloudfunctions.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudkms.googleapis.com",
  ]
}

variable "vpc_accessible_services_restriction" {
  description = "Enable restriction on VPC accessible services"
  type        = bool
  default     = true
}

variable "vpc_accessible_services" {
  description = "List of services accessible from within the perimeter"
  type        = list(string)
  default = [
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "compute.googleapis.com",
    "pubsub.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudkms.googleapis.com",
  ]
}

variable "ingress_from_identity_type" {
  description = "Identity type for ingress policies"
  type        = string
  default     = "IDENTITY_TYPE_UNSPECIFIED"
}

variable "ingress_source_resource" {
  description = "Resource for ingress policy source"
  type        = string
  default     = ""
}

variable "ingress_to_resources" {
  description = "Resources for ingress policy destination"
  type        = list(string)
  default     = []
}

variable "ingress_to_service_name" {
  description = "Service name for ingress policy destination"
  type        = string
  default     = "storage.googleapis.com"
}

variable "ingress_to_method" {
  description = "Method for ingress policy destination"
  type        = string
  default     = "*"
}

variable "egress_from_identity_type" {
  description = "Identity type for egress policies"
  type        = string
  default     = "IDENTITY_TYPE_UNSPECIFIED"
}

variable "egress_to_resources" {
  description = "Resources for egress policy destination"
  type        = list(string)
  default     = []
}

variable "egress_to_service_name" {
  description = "Service name for egress policy destination"
  type        = string
  default     = "storage.googleapis.com"
}

variable "egress_to_method" {
  description = "Method for egress policy destination"
  type        = string
  default     = "*"
}

variable "use_explicit_dry_run_spec" {
  description = "Use explicit dry run spec for the service perimeter"
  type        = bool
  default     = false
}

variable "access_levels" {
  description = "Map of access level configurations. Each key is the access level name."
  type = map(object({
    combining_function     = string
    ip_subnetworks         = list(string)
    required_access_levels = list(string)
    members                = list(string)
    negate                 = bool
    require_screen_lock    = bool
    require_admin_approval = bool
    os_type                = string
    minimum_version        = string
    regions                = list(string)
  }))
  default = {}
}

variable "ingress_policies" {
  description = "Map of ingress policy configurations. Each key is the policy name."
  type = map(object({
    ingress_from_identity_type  = string
    ingress_source_access_level = string
    ingress_source_resource     = string
    ingress_to_resources        = list(string)
    ingress_to_service_name     = string
    ingress_to_method           = string
    ingress_to_permission       = string
  }))
  default = {}
}

variable "egress_policies" {
  description = "Map of egress policy configurations. Each key is the policy name."
  type = map(object({
    egress_from_identity_type = string
    egress_to_resources       = list(string)
    egress_to_service_name    = string
    egress_to_method          = string
    egress_to_permission      = string
  }))
  default = {}
}
