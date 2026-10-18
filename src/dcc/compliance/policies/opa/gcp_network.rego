# OPA/Rego Policy: GCP Network Security Compliance
# Ensures GCP network security best practices
package dcc.gcp.network

import future.keywords.if
import future.keywords.in

# Deny GCS buckets with public access
deny contains msg if {
    some bucket in input.gcp.storage.buckets
    bucket.public_access_prevention != "enforced"
    msg := sprintf("GCS bucket '%s' does not enforce public access prevention", [bucket.name])
}

# Deny VPC subnets without flow logs
deny contains msg if {
    some subnet in input.gcp.compute.subnetworks
    not subnet.flow_logs_enabled
    msg := sprintf("VPC subnet '%s' does not have flow logs enabled", [subnet.name])
}

# Deny GKE clusters without private endpoint
deny contains msg if {
    some cluster in input.gcp.container.clusters
    not cluster.private_endpoint_enabled
    msg := sprintf("GKE cluster '%s' does not have private endpoint enabled", [cluster.name])
}
