# encryption.rego — Encryption governance for Data Center Commander
package datacenter.encryption

import data.common

# --- Rule: Production resources must have encryption at rest ---
deny contains msg if {
    common.is_production
    not common.encrypted_at_rest
    msg := sprintf("CRITICAL: Production resource '%s' must have encryption at rest enabled", [input.resource_id])
}

# --- Rule: Production resources must have encryption in transit ---
deny contains msg if {
    common.is_production
    not common.encrypted_in_transit
    msg := sprintf("CRITICAL: Production resource '%s' must have encryption in transit enabled", [input.resource_id])
}

# --- Rule: Staging resources must have encryption at rest ---
deny contains msg if {
    common.is_staging
    not common.encrypted_at_rest
    msg := sprintf("HIGH: Staging resource '%s' must have encryption at rest enabled", [input.resource_id])
}

# --- Rule: Staging resources must have encryption in transit ---
deny contains msg if {
    common.is_staging
    not common.encrypted_in_transit
    msg := sprintf("HIGH: Staging resource '%s' must have encryption in transit enabled", [input.resource_id])
}

# --- Rule: Resources with sensitive data must have encryption at rest ---
deny contains msg if {
    common.has_data_classification
    input.tags["data_classification"] == "sensitive"
    not common.encrypted_at_rest
    msg := sprintf("CRITICAL: Resource '%s' with sensitive data must have encryption at rest", [input.resource_id])
}

# --- Rule: Resources with confidential data must have encryption at rest ---
deny contains msg if {
    common.has_data_classification
    input.tags["data_classification"] == "confidential"
    not common.encrypted_at_rest
    msg := sprintf("CRITICAL: Resource '%s' with confidential data must have encryption at rest", [input.resource_id])
}

# --- Rule: Resources with restricted data must have encryption at rest ---
deny contains msg if {
    common.has_data_classification
    input.tags["data_classification"] == "restricted"
    not common.encrypted_at_rest
    msg := sprintf("CRITICAL: Resource '%s' with restricted data must have encryption at rest", [input.resource_id])
}

# --- Rule: Resources with sensitive data must have encryption in transit ---
deny contains msg if {
    common.has_data_classification
    input.tags["data_classification"] == "sensitive"
    not common.encrypted_in_transit
    msg := sprintf("CRITICAL: Resource '%s' with sensitive data must have encryption in transit", [input.resource_id])
}

# --- Rule: Resources with confidential data must have encryption in transit ---
deny contains msg if {
    common.has_data_classification
    input.tags["data_classification"] == "confidential"
    not common.encrypted_in_transit
    msg := sprintf("CRITICAL: Resource '%s' with confidential data must have encryption in transit", [input.resource_id])
}

# --- Rule: Resources with restricted data must have encryption in transit ---
deny contains msg if {
    common.has_data_classification
    input.tags["data_classification"] == "restricted"
    not common.encrypted_in_transit
    msg := sprintf("CRITICAL: Resource '%s' with restricted data must have encryption in transit", [input.resource_id])
}

# --- Rule: Production resources must use AES-256 encryption ---
deny contains msg if {
    common.is_production
    common.encrypted_at_rest
    input.encryption.algorithm != "AES-256"
    msg := sprintf("HIGH: Production resource '%s' must use AES-256 encryption at rest", [input.resource_id])
}

# --- Rule: Production resources must not use TLS 1.0 for encryption in transit ---
deny contains msg if {
    common.is_production
    common.encrypted_in_transit
    input.encryption.tls_version == "TLSv1.0"
    msg := sprintf("CRITICAL: Production resource '%s' must not use TLS 1.0 for encryption in transit", [input.resource_id])
}

# --- Rule: Production resources must not use TLS 1.1 for encryption in transit ---
deny contains msg if {
    common.is_production
    common.encrypted_in_transit
    input.encryption.tls_version == "TLSv1.1"
    msg := sprintf("HIGH: Production resource '%s' should not use TLS 1.1 for encryption in transit", [input.resource_id])
}

# --- Rule: Resources must not use DES encryption ---
deny contains msg if {
    input.encryption.algorithm == "DES"
    msg := sprintf("CRITICAL: Resource '%s' uses DES encryption which is insecure", [input.resource_id])
}

# --- Rule: Resources must not use 3DES encryption ---
deny contains msg if {
    input.encryption.algorithm == "3DES"
    msg := sprintf("HIGH: Resource '%s' uses 3DES encryption which is weak", [input.resource_id])
}

# --- Rule: Resources must not use RC4 encryption ---
deny contains msg if {
    input.encryption.algorithm == "RC4"
    msg := sprintf("CRITICAL: Resource '%s' uses RC4 encryption which is insecure", [input.resource_id])
}

# --- Rule: Resources must not use MD5 for hashing ---
deny contains msg if {
    input.encryption.hash_algorithm == "MD5"
    msg := sprintf("CRITICAL: Resource '%s' uses MD5 hashing which is insecure", [input.resource_id])
}

# --- Rule: Resources must not use SHA-1 for hashing ---
deny contains msg if {
    input.encryption.hash_algorithm == "SHA-1"
    msg := sprintf("HIGH: Resource '%s' uses SHA-1 hashing which is weak", [input.resource_id])
}

# --- Rule: Resources must not use ECB mode ---
deny contains msg if {
    input.encryption.mode == "ECB"
    msg := sprintf("CRITICAL: Resource '%s' uses ECB mode which is insecure", [input.resource_id])
}

# --- Rule: Resources must not use CBC mode without HMAC ---
deny contains msg if {
    input.encryption.mode == "CBC"
    input.encryption.hmac_enabled != true
    msg := sprintf("HIGH: Resource '%s' uses CBC mode without HMAC", [input.resource_id])
}

# --- Rule: Resources must not use static encryption keys ---
deny contains msg if {
    input.encryption.key_rotation == false
    msg := sprintf("HIGH: Resource '%s' does not have encryption key rotation enabled", [input.resource_id])
}

# --- Rule: Production resources must rotate encryption keys every 90 days ---
deny contains msg if {
    common.is_production
    input.encryption.key_rotation == true
    input.encryption.key_rotation_days > 90
    msg := sprintf("HIGH: Production resource '%s' rotates encryption keys every %d days (max 90)", [input.resource_id, input.encryption.key_rotation_days])
}

# --- Rule: Resources must not have expired encryption keys ---
deny contains msg if {
    input.encryption.key_expiry_days <= 0
    msg := sprintf("CRITICAL: Resource '%s' has expired encryption keys", [input.resource_id])
}

# --- Rule: Resources must not have encryption keys expiring within 30 days ---
deny contains msg if {
    input.encryption.key_expiry_days <= 30
    msg := sprintf("HIGH: Resource '%s' has encryption keys expiring in %d days", [input.resource_id, input.encryption.key_expiry_days])
}

# --- Rule: Resources must not have encryption keys older than 1 year ---
deny contains msg if {
    input.encryption.key_age_days > 365
    msg := sprintf("MEDIUM: Resource '%s' has encryption keys older than 1 year (%d days)", [input.resource_id, input.encryption.key_age_days])
}

# --- Rule: Resources must not use self-signed certificates ---
deny contains msg if {
    input.encryption.certificate_type == "self-signed"
    msg := sprintf("HIGH: Resource '%s' uses a self-signed certificate", [input.resource_id])
}

# --- Rule: Production resources must not use wildcard certificates ---
deny contains msg if {
    common.is_production
    input.encryption.certificate_type == "wildcard"
    msg := sprintf("MEDIUM: Production resource '%s' uses a wildcard certificate", [input.resource_id])
}

# --- Rule: Resources must not have expired certificates ---
deny contains msg if {
    input.encryption.certificate_expiry_days <= 0
    msg := sprintf("CRITICAL: Resource '%s' has an expired certificate", [input.resource_id])
}

# --- Rule: Resources must not have certificates expiring within 30 days ---
deny contains msg if {
    input.encryption.certificate_expiry_days <= 30
    msg := sprintf("HIGH: Resource '%s' has a certificate expiring in %d days", [input.resource_id, input.encryption.certificate_expiry_days])
}

# --- Rule: Resources must not use certificates with weak key sizes ---
deny contains msg if {
    input.encryption.certificate_key_size < 2048
    msg := sprintf("HIGH: Resource '%s' uses a certificate with key size %d (min 2048)", [input.resource_id, input.encryption.certificate_key_size])
}

# --- Rule: Resources must not use certificates with SHA-1 signature ---
deny contains msg if {
    input.encryption.certificate_signature == "SHA-1"
    msg := sprintf("HIGH: Resource '%s' uses a certificate with SHA-1 signature", [input.resource_id])
}

# --- Rule: Resources must not use certificates with MD5 signature ---
deny contains msg if {
    input.encryption.certificate_signature == "MD5"
    msg := sprintf("CRITICAL: Resource '%s' uses a certificate with MD5 signature", [input.resource_id])
}

# --- Rule: Resources must not use certificates with DSA key algorithm ---
deny contains msg if {
    input.encryption.certificate_key_algorithm == "DSA"
    msg := sprintf("HIGH: Resource '%s' uses DSA certificate key algorithm which is weak", [input.resource_id])
}

# --- Rule: Resources must not use certificates with DH key algorithm ---
deny contains msg if {
    input.encryption.certificate_key_algorithm == "DH"
    msg := sprintf("HIGH: Resource '%s' uses DH certificate key algorithm which is weak", [input.resource_id])
}
