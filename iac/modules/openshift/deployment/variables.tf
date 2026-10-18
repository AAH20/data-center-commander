variable "name" {
  description = "Name of the deployment"
  type        = string
}

variable "namespace" {
  description = "Namespace to deploy into"
  type        = string
}

variable "image" {
  description = "Container image to deploy"
  type        = string
}

variable "image_pull_policy" {
  description = "Image pull policy"
  type        = string
  default     = "IfNotPresent"
}

variable "replicas" {
  description = "Number of replicas"
  type        = number
  default     = 2
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
  description = "Additional annotations"
  type        = map(string)
  default     = {}
}

variable "pod_annotations" {
  description = "Additional pod annotations"
  type        = map(string)
  default     = {}
}

variable "service_account_name" {
  description = "Service account name for the pods"
  type        = string
  default     = "default"
}

variable "container_port" {
  description = "Container port"
  type        = number
  default     = 8790
}

variable "run_as_user" {
  description = "UID to run the container as"
  type        = number
  default     = 999
}

variable "run_as_group" {
  description = "GID to run the container as"
  type        = number
  default     = 999
}

variable "fs_group" {
  description = "FS group for the container"
  type        = number
  default     = 999
}

variable "cpu_request" {
  description = "CPU request"
  type        = string
  default     = "100m"
}

variable "memory_request" {
  description = "Memory request"
  type        = string
  default     = "128Mi"
}

variable "cpu_limit" {
  description = "CPU limit"
  type        = string
  default     = "500m"
}

variable "memory_limit" {
  description = "Memory limit"
  type        = string
  default     = "256Mi"
}

variable "max_surge" {
  description = "Max surge for rolling update"
  type        = string
  default     = "1"
}

variable "max_unavailable" {
  description = "Max unavailable for rolling update"
  type        = string
  default     = "0"
}

variable "config_data" {
  description = "ConfigMap data (non-sensitive configuration)"
  type        = map(string)
  default     = {}
}

variable "secret_data" {
  description = "Secret data (sensitive configuration)"
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "env_vars" {
  description = "Environment variables (plain values)"
  type        = map(string)
  default     = {}
}

variable "secret_env_vars" {
  description = "Environment variables from secrets (map of env_name -> secret_key)"
  type        = map(string)
  default     = {}
}

variable "volume_mounts" {
  description = "Volume mounts (map of name -> mount_path)"
  type        = map(string)
  default     = {}
}

variable "liveness_probe_path" {
  description = "Path for liveness probe"
  type        = string
  default     = "/healthz"
}

variable "liveness_initial_delay" {
  description = "Initial delay for liveness probe"
  type        = number
  default     = 10
}

variable "liveness_period" {
  description = "Period for liveness probe"
  type        = number
  default     = 30
}

variable "liveness_timeout" {
  description = "Timeout for liveness probe"
  type        = number
  default     = 5
}

variable "liveness_failure_threshold" {
  description = "Failure threshold for liveness probe"
  type        = number
  default     = 3
}

variable "readiness_probe_path" {
  description = "Path for readiness probe"
  type        = string
  default     = "/readyz"
}

variable "readiness_initial_delay" {
  description = "Initial delay for readiness probe"
  type        = number
  default     = 5
}

variable "readiness_period" {
  description = "Period for readiness probe"
  type        = number
  default     = 10
}

variable "readiness_timeout" {
  description = "Timeout for readiness probe"
  type        = number
  default     = 5
}

variable "readiness_failure_threshold" {
  description = "Failure threshold for readiness probe"
  type        = number
  default     = 3
}

variable "enable_metrics" {
  description = "Enable Prometheus metrics scraping"
  type        = bool
  default     = false
}

variable "metrics_path" {
  description = "Metrics endpoint path"
  type        = string
  default     = "/metrics"
}

variable "enable_hpa" {
  description = "Enable HorizontalPodAutoscaler"
  type        = bool
  default     = false
}

variable "hpa_min_replicas" {
  description = "Minimum replicas for HPA"
  type        = number
  default     = 2
}

variable "hpa_max_replicas" {
  description = "Maximum replicas for HPA"
  type        = number
  default     = 10
}

variable "hpa_cpu_target" {
  description = "CPU utilization target for HPA"
  type        = number
  default     = 70
}

variable "hpa_memory_target" {
  description = "Memory utilization target for HPA"
  type        = number
  default     = 80
}

variable "enable_pdb" {
  description = "Enable PodDisruptionBudget"
  type        = bool
  default     = false
}

variable "pdb_min_available" {
  description = "Minimum available pods for PDB"
  type        = string
  default     = "1"
}

variable "topology_spread_constraints" {
  description = "Topology spread constraints for pod scheduling"
  type = list(object({
    max_skew           = number
    topology_key       = string
    when_unsatisfiable = string
  }))
  default = [{
    max_skew           = 1
    topology_key       = "topology.kubernetes.io/zone"
    when_unsatisfiable = "ScheduleAnyway"
  }]
}
