# OPA/Rego Policy: AWS Encryption Compliance
# Ensures all AWS storage resources have encryption at rest enabled
package dcc.aws.encryption

import future.keywords.if
import future.keywords.in

# Deny S3 buckets without server-side encryption
deny contains msg if {
    some bucket in input.aws.s3.buckets
    not bucket.server_side_encryption_configuration
    msg := sprintf("S3 bucket '%s' does not have server-side encryption configured", [bucket.name])
}

# Deny RDS instances without storage encryption
deny contains msg if {
    some instance in input.aws.rds.instances
    not instance.storage_encrypted
    msg := sprintf("RDS instance '%s' does not have storage encryption enabled", [instance.id])
}

# Deny EBS volumes without encryption
deny contains msg if {
    some volume in input.aws.ec2.volumes
    not volume.encrypted
    msg := sprintf("EBS volume '%s' is not encrypted", [volume.id])
}

# Deny DynamoDB tables without encryption
deny contains msg if {
    some table in input.aws.dynamodb.tables
    not table.sse_enabled
    msg := sprintf("DynamoDB table '%s' does not have SSE enabled", [table.name])
}
