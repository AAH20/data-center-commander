# =============================================================================
# GCP Network Module — Provider Configuration
# =============================================================================
# This module owns its Google provider configuration because it is the only
# place `var.common_tags` can be turned into labels.
#
# None of the resource types used here accept a `labels` argument (verified
# against the hashicorp/google 5.x schema: google_compute_network,
# google_compute_subnetwork, google_compute_firewall, google_compute_router and
# google_compute_router_nat have no `labels` attribute), so `default_labels` on
# the provider is the GCP-appropriate equivalent of the `common_tags` pattern
# used by the AWS/Azure modules.
#
# Consequence: because this module configures its own google provider, callers
# must NOT pass `providers = { google = ... }` -- Terraform rejects that with
# "Cannot override provider configuration". Project and region are taken from
# the module's own variables instead.
# =============================================================================

provider "google" {
  project        = var.project_id
  region         = var.region
  default_labels = var.common_tags
}
