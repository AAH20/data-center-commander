# tfsec policy: GCP encryption compliance
package custom.gcp.encryption

import data.lib.result

# Deny GCS buckets without uniform access
deny[res] {
	bucket := input.gcp.storage.bucket[_]
	not bucket.uniform_bucket_level_access
	msg := "GCS bucket does not use uniform bucket-level access"
	res := result.new(msg, bucket)
}

# Deny GKE clusters without network policy
deny[res] {
	cluster := input.gcp.container.cluster[_]
	not cluster.network_policy_enabled
	msg := "GKE cluster does not have network policy enabled"
	res := result.new(msg, cluster)
}
