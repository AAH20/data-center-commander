# OPA/Rego Policy: GCP Encryption Compliance
# Ensures GCP resources have encryption enabled
package dcc.gcp.encryption

import future.keywords.if
import future.keywords.in

# Deny GCS buckets without uniform bucket-level access
deny contains msg if {
    some bucket in input.gcp.storage.buckets
    not bucket.uniform_bucket_level_access
    msg := sprintf("GCS bucket '%s' does not use uniform bucket-level access", [bucket.name])
}

# Deny GCE instances without Shielded VM
deny contains msg if {
    some instance in input.gcp.compute.instances
    not instance.shielded_instance_config
    msg := sprintf("GCE instance '%s' does not use Shielded VM features", [instance.name])
}

# Deny GKE clusters without network policy
deny contains msg if {
    some cluster in input.gcp.container.clusters
    not cluster.network_policy_enabled
    msg := sprintf("GKE cluster '%s' does not have network policy enabled", [cluster.name])
}
