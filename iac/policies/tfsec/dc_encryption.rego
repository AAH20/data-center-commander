# Data Center Custom Rule: Encryption
# Ensures data center resources use encryption for data protection
package custom.aws.encryption

import data.lib.result

# Rule: AWS S3 buckets used for config delivery must have encryption
deny[res] {
	bucket := input.aws.s3.bucket[_]
	not bucket.server_side_encryption_configuration
	msg := "S3 bucket does not have server-side encryption configured. Data center policy requires encryption for all S3 buckets."
	res := result.new(msg, bucket)
}

# Rule: AWS S3 buckets must have versioning enabled
deny[res] {
	bucket := input.aws.s3.bucket[_]
	bucket.versioning.enabled.value == false
	msg := "S3 bucket does not have versioning enabled. Data center policy requires versioning for data protection and recovery."
	res := result.new(msg, bucket)
}

# Rule: AWS S3 buckets must have public access blocked
deny[res] {
	bucket := input.aws.s3.bucket[_]
	bucket.public_access_block.block_public_acls.value == false
	msg := "S3 bucket does not block public ACLs. Data center policy requires all S3 buckets to block public access."
	res := result.new(msg, bucket)
}

# Rule: AWS CloudWatch log groups should have KMS encryption
warn[res] {
	log_group := input.aws.cloudwatch.loggroup[_]
	not log_group.kms_key_id
	msg := "CloudWatch log group does not have KMS encryption. Data center policy recommends KMS encryption for log data at rest."
	res := result.new(msg, log_group)
}

# Rule: libvirt volumes should use qcow2 format with encryption
warn[res] {
	volume := input.libvirt.volume[_]
	volume.format.value != "qcow2"
	msg := "libvirt volume does not use qcow2 format. Data center policy recommends qcow2 for snapshot and encryption support."
	res := result.new(msg, volume)
}
