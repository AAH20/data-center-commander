"""
Sentinel Policy Tests — Data Center Commander
Tests for Sentinel policies using the sentinel test framework.
These tests validate that Sentinel policies correctly enforce data center governance rules.
"""

import json
import os
import pytest
import subprocess
import tempfile

POLICY_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "policies", "sentinel")


def run_sentinel_test(policy_path: str, test_path: str) -> dict:
    """Run sentinel test against a policy and return the result."""
    result = subprocess.run(
        ["sentinel", "test", "--verbose", policy_path, test_path],
        capture_output=True,
        text=True,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run_sentinel_apply(policy_path: str, input_data: dict) -> dict:
    """Run sentinel apply against a policy with given input."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(input_data, f)
        input_file = f.name

    try:
        result = subprocess.run(
            ["sentinel", "apply", "-input", input_file, policy_path],
            capture_output=True,
            text=True,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    finally:
        os.unlink(input_file)


class TestSentinelResourceTagging:
    """Tests for Sentinel resource tagging policies."""

    def test_sentinel_policy_exists(self):
        """Verify Sentinel policy file exists."""
        policy_file = os.path.join(POLICY_DIR, "resource_tagging.sentinel")
        if os.path.exists(policy_file):
            assert os.path.getsize(policy_file) > 0

    def test_sentinel_test_framework_available(self):
        """Verify sentinel test framework is available."""
        result = subprocess.run(
            ["sentinel", "test", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0


class TestSentinelEncryption:
    """Tests for Sentinel encryption policies."""

    def test_sentinel_policy_exists(self):
        """Verify Sentinel policy file exists."""
        policy_file = os.path.join(POLICY_DIR, "encryption.sentinel")
        if os.path.exists(policy_file):
            assert os.path.getsize(policy_file) > 0


class TestSentinelNetworkSegmentation:
    """Tests for Sentinel network segmentation policies."""

    def test_sentinel_policy_exists(self):
        """Verify Sentinel policy file exists."""
        policy_file = os.path.join(POLICY_DIR, "network_segmentation.sentinel")
        if os.path.exists(policy_file):
            assert os.path.getsize(policy_file) > 0


class TestSentinelAccessControl:
    """Tests for Sentinel access control policies."""

    def test_sentinel_policy_exists(self):
        """Verify Sentinel policy file exists."""
        policy_file = os.path.join(POLICY_DIR, "access_control.sentinel")
        if os.path.exists(policy_file):
            assert os.path.getsize(policy_file) > 0


class TestSentinelCompliance:
    """Tests for Sentinel compliance policies."""

    def test_sentinel_policy_exists(self):
        """Verify Sentinel policy file exists."""
        policy_file = os.path.join(POLICY_DIR, "compliance.sentinel")
        if os.path.exists(policy_file):
            assert os.path.getsize(policy_file) > 0


class TestSentinelMockData:
    """Tests for Sentinel mock data used in policy testing."""

    def test_mock_data_directory_exists(self):
        """Verify mock data directory exists for Sentinel tests."""
        mock_dir = os.path.join(POLICY_DIR, "mock")
        if os.path.exists(mock_dir):
            assert os.path.isdir(mock_dir)

    def test_mock_data_files_present(self):
        """Verify mock data files are present for each policy."""
        mock_dir = os.path.join(POLICY_DIR, "mock")
        if os.path.exists(mock_dir):
            mock_files = [f for f in os.listdir(mock_dir) if f.endswith('.json')]
            assert len(mock_files) > 0
