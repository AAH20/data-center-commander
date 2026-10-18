variable "name" {
  description = "Name of the route"
  type        = string
}

variable "namespace" {
  description = "Namespace for the route"
  type        = string
}

variable "host" {
  description = "Hostname for the route (e.g. dcc.example.com). Leave empty for auto-generated."
  type        = string
  default     = ""
}

variable "path" {
  description = "Path for the route"
  type        = string
  default     = "/"
}

variable "service_name" {
  description = "Name of the target Service"
  type        = string
}

variable "service_port" {
  description = "Target port on the Service (name or number)"
  type        = string
  default     = "http"
}

variable "tls_termination" {
  description = "TLS termination type (edge, passthrough, reencrypt)"
  type        = string
  default     = "edge"

  validation {
    condition     = contains(["edge", "passthrough", "reencrypt"], var.tls_termination)
    error_message = "Must be edge, passthrough, or reencrypt."
  }
}

variable "insecure_policy" {
  description = "Insecure traffic policy (Allow, Disable, Redirect)"
  type        = string
  default     = "Redirect"

  validation {
    condition     = contains(["Allow", "Disable", "Redirect"], var.insecure_policy)
    error_message = "Must be Allow, Disable, or Redirect."
  }
}

variable "tls_certificate" {
  description = "TLS certificate (PEM). Required for edge/reencrypt."
  type        = string
  default     = null
  sensitive   = true
}

variable "tls_key" {
  description = "TLS private key (PEM). Required for edge/reencrypt."
  type        = string
  default     = null
  sensitive   = true
}

variable "tls_ca_certificate" {
  description = "TLS CA certificate (PEM)"
  type        = string
  default     = null
  sensitive   = true
}

variable "destination_ca_certificate" {
  description = "Destination CA certificate for reencrypt termination"
  type        = string
  default     = null
  sensitive   = true
}

variable "wildcard_policy" {
  description = "Wildcard policy (None, Subdomain)"
  type        = string
  default     = "None"

  validation {
    condition     = contains(["None", "Subdomain"], var.wildcard_policy)
    error_message = "Must be None or Subdomain."
  }
}

variable "part_of" {
  description = "Value for app.kubernetes.io/part-of label"
  type        = string
  default     = "data-center-commander"
}

variable "labels" {
  description = "Additional labels"
  type        = map(string)
  default     = {}
}

variable "annotations" {
  description = "Additional annotations (e.g. for router sharding)"
  type        = map(string)
  default     = {}
}
