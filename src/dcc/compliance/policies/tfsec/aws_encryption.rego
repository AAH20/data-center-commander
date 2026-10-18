# tfsec policy: AWS encryption compliance
package custom.aws.encryption

import data.lib.result

# Deny S3 buckets without encryption
deny[res] {
	bucket := input.aws.s3.bucket[_]
	not bucket.server_side_encryption_configuration
	msg := "S3 bucket does not have server-side encryption configured"
	res := result.new(msg, bucket)
}

# Deny RDS instances without encryption
deny[res] {
	instance := input.aws.rds.instance[_]
	not instance.storage_encrypted
	msg := "RDS instance does not have storage encryption enabled"
	res := result.new(msg, instance)
}

# Deny EBS volumes without encryption
deny[res] {
	volume := input.aws.ec2.volume[_]
	not volume.encrypted
	msg := "EBS volume is not encrypted"
	res := result.new(msg, volume)
}
