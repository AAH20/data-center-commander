"""
OPA/Rego Policy Tests — Encryption
Tests for datacenter.encryption package.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from helpers import make_resource, run_opa  # noqa: E402,I001 — sys.path must be set before importing local helpers


class TestEncryptionCompliance:
    """Tests for encryption policy compliance."""

    def test_fully_compliant_resource_passes(self):
        """A resource with all encryption settings should produce no violations."""
        resource = make_resource()
        result = run_opa(resource, "datacenter.encryption")
        assert result.get("result", [{}])[0].get("expressions", [{}])[0].get("value", []) == []

    def test_production_missing_encryption_at_rest_fails(self):
        """Production resource without encryption at rest should be denied."""
        resource = make_resource()
        resource["encryption"]["at_rest"] = False
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("encryption at rest" in d for d in denies)

    def test_production_missing_encryption_in_transit_fails(self):
        """Production resource without encryption in transit should be denied."""
        resource = make_resource()
        resource["encryption"]["in_transit"] = False
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("encryption in transit" in d for d in denies)

    def test_staging_missing_encryption_at_rest_fails(self):
        """Staging resource without encryption at rest should be denied."""
        resource = make_resource(environment="staging")
        resource["encryption"]["at_rest"] = False
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("encryption at rest" in d for d in denies)

    def test_staging_missing_encryption_in_transit_fails(self):
        """Staging resource without encryption in transit should be denied."""
        resource = make_resource(environment="staging")
        resource["encryption"]["in_transit"] = False
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("encryption in transit" in d for d in denies)

    def test_sensitive_data_missing_encryption_at_rest_fails(self):
        """Resource with sensitive data without encryption at rest should be denied."""
        resource = make_resource()
        resource["tags"]["data_classification"] = "sensitive"
        resource["encryption"]["at_rest"] = False
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("sensitive" in d and "encryption at rest" in d for d in denies)

    def test_confidential_data_missing_encryption_at_rest_fails(self):
        """Resource with confidential data without encryption at rest should be denied."""
        resource = make_resource()
        resource["tags"]["data_classification"] = "confidential"
        resource["encryption"]["at_rest"] = False
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("confidential" in d and "encryption at rest" in d for d in denies)

    def test_restricted_data_missing_encryption_at_rest_fails(self):
        """Resource with restricted data without encryption at rest should be denied."""
        resource = make_resource()
        resource["tags"]["data_classification"] = "restricted"
        resource["encryption"]["at_rest"] = False
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("restricted" in d and "encryption at rest" in d for d in denies)

    def test_sensitive_data_missing_encryption_in_transit_fails(self):
        """Resource with sensitive data without encryption in transit should be denied."""
        resource = make_resource()
        resource["tags"]["data_classification"] = "sensitive"
        resource["encryption"]["in_transit"] = False
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("sensitive" in d and "encryption in transit" in d for d in denies)

    def test_confidential_data_missing_encryption_in_transit_fails(self):
        """Resource with confidential data without encryption in transit should be denied."""
        resource = make_resource()
        resource["tags"]["data_classification"] = "confidential"
        resource["encryption"]["in_transit"] = False
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("confidential" in d and "encryption in transit" in d for d in denies)

    def test_restricted_data_missing_encryption_in_transit_fails(self):
        """Resource with restricted data without encryption in transit should be denied."""
        resource = make_resource()
        resource["tags"]["data_classification"] = "restricted"
        resource["encryption"]["in_transit"] = False
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("restricted" in d and "encryption in transit" in d for d in denies)

    def test_production_non_aes256_fails(self):
        """Production resource not using AES-256 should be denied."""
        resource = make_resource()
        resource["encryption"]["algorithm"] = "AES-128"
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("AES-256" in d for d in denies)

    def test_production_tls10_fails(self):
        """Production resource using TLS 1.0 should be denied."""
        resource = make_resource()
        resource["encryption"]["tls_version"] = "TLSv1.0"
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("TLS 1.0" in d for d in denies)

    def test_production_tls11_fails(self):
        """Production resource using TLS 1.1 should be denied."""
        resource = make_resource()
        resource["encryption"]["tls_version"] = "TLSv1.1"
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("TLS 1.1" in d for d in denies)

    def test_des_encryption_fails(self):
        """Resource using DES encryption should be denied."""
        resource = make_resource()
        resource["encryption"]["algorithm"] = "DES"
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("DES" in d for d in denies)

    def test_3des_encryption_fails(self):
        """Resource using 3DES encryption should be denied."""
        resource = make_resource()
        resource["encryption"]["algorithm"] = "3DES"
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("3DES" in d for d in denies)

    def test_rc4_encryption_fails(self):
        """Resource using RC4 encryption should be denied."""
        resource = make_resource()
        resource["encryption"]["algorithm"] = "RC4"
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("RC4" in d for d in denies)

    def test_md5_hashing_fails(self):
        """Resource using MD5 hashing should be denied."""
        resource = make_resource()
        resource["encryption"]["hash_algorithm"] = "MD5"
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("MD5" in d for d in denies)

    def test_sha1_hashing_fails(self):
        """Resource using SHA-1 hashing should be denied."""
        resource = make_resource()
        resource["encryption"]["hash_algorithm"] = "SHA-1"
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("SHA-1" in d for d in denies)

    def test_ecb_mode_fails(self):
        """Resource using ECB mode should be denied."""
        resource = make_resource()
        resource["encryption"]["mode"] = "ECB"
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("ECB" in d for d in denies)

    def test_cbc_mode_without_hmac_fails(self):
        """Resource using CBC mode without HMAC should be denied."""
        resource = make_resource()
        resource["encryption"]["mode"] = "CBC"
        resource["encryption"]["hmac_enabled"] = False
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("CBC" in d and "HMAC" in d for d in denies)

    def test_no_key_rotation_fails(self):
        """Resource without key rotation should be denied."""
        resource = make_resource()
        resource["encryption"]["key_rotation"] = False
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("key rotation" in d for d in denies)

    def test_production_key_rotation_over_90_days_fails(self):
        """Production resource with key rotation > 90 days should be denied."""
        resource = make_resource()
        resource["encryption"]["key_rotation_days"] = 180
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("90" in d for d in denies)

    def test_expired_encryption_keys_fails(self):
        """Resource with expired encryption keys should be denied."""
        resource = make_resource()
        resource["encryption"]["key_expiry_days"] = 0
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("expired" in d for d in denies)

    def test_encryption_keys_expiring_within_30_days_fails(self):
        """Resource with encryption keys expiring within 30 days should be denied."""
        resource = make_resource()
        resource["encryption"]["key_expiry_days"] = 15
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("expiring" in d for d in denies)

    def test_encryption_keys_older_than_1_year_fails(self):
        """Resource with encryption keys older than 1 year should be denied."""
        resource = make_resource()
        resource["encryption"]["key_age_days"] = 400
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("older than 1 year" in d for d in denies)

    def test_self_signed_certificate_fails(self):
        """Resource using self-signed certificate should be denied."""
        resource = make_resource()
        resource["encryption"]["certificate_type"] = "self-signed"
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("self-signed" in d for d in denies)

    def test_production_wildcard_certificate_fails(self):
        """Production resource using wildcard certificate should be denied."""
        resource = make_resource()
        resource["encryption"]["certificate_type"] = "wildcard"
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("wildcard" in d for d in denies)

    def test_expired_certificate_fails(self):
        """Resource with expired certificate should be denied."""
        resource = make_resource()
        resource["encryption"]["certificate_expiry_days"] = 0
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("expired certificate" in d for d in denies)

    def test_certificate_expiring_within_30_days_fails(self):
        """Resource with certificate expiring within 30 days should be denied."""
        resource = make_resource()
        resource["encryption"]["certificate_expiry_days"] = 15
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("expiring" in d for d in denies)

    def test_weak_certificate_key_size_fails(self):
        """Resource with certificate key size < 2048 should be denied."""
        resource = make_resource()
        resource["encryption"]["certificate_key_size"] = 1024
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("key size" in d for d in denies)

    def test_sha1_certificate_signature_fails(self):
        """Resource with SHA-1 certificate signature should be denied."""
        resource = make_resource()
        resource["encryption"]["certificate_signature"] = "SHA-1"
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("SHA-1" in d for d in denies)

    def test_md5_certificate_signature_fails(self):
        """Resource with MD5 certificate signature should be denied."""
        resource = make_resource()
        resource["encryption"]["certificate_signature"] = "MD5"
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("MD5" in d for d in denies)

    def test_dsa_certificate_key_algorithm_fails(self):
        """Resource with DSA certificate key algorithm should be denied."""
        resource = make_resource()
        resource["encryption"]["certificate_key_algorithm"] = "DSA"
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("DSA" in d for d in denies)

    def test_dh_certificate_key_algorithm_fails(self):
        """Resource with DH certificate key algorithm should be denied."""
        resource = make_resource()
        resource["encryption"]["certificate_key_algorithm"] = "DH"
        result = run_opa(resource, "datacenter.encryption")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("DH" in d for d in denies)
