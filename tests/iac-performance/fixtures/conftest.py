"""
Fixtures for IaC performance tests.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.checkov_utils import CheckovRunner
from utils.rego_utils import OpaRunner, create_opa_input
from utils.terraform_utils import TerraformRunner

# Path to the project's policy directories
PROJECT_ROOT = Path(__file__).parent.parent.parent
REGO_POLICY_DIR = PROJECT_ROOT / "policies" / "rego"
CHECKOV_POLICY_DIR = PROJECT_ROOT / "policies" / "checkov"


@pytest.fixture(scope="session")
def terraform_bin():
    """Get terraform binary path from env or default."""
    return os.environ.get("TERRAFORM_BIN", "terraform")


@pytest.fixture(scope="session")
def opa_bin():
    """Get OPA binary path from env or default."""
    return os.environ.get("OPA_BIN", "opa")


@pytest.fixture(scope="session")
def checkov_bin():
    """Get checkov binary path from env or default."""
    return os.environ.get("CHECKOV_BIN", "checkov")


@pytest.fixture(scope="session")
def terraform_runner(terraform_bin):
    """Create a TerraformRunner instance."""
    # Use a temporary directory for the runner
    tmpdir = tempfile.mkdtemp(prefix="tf_runner_")
    try:
        runner = TerraformRunner(tmpdir, terraform_bin=terraform_bin)
        yield runner
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture(scope="session")
def opa_runner(opa_bin):
    """Create an OpaRunner instance."""
    runner = OpaRunner(opa_bin=opa_bin)
    yield runner


@pytest.fixture(scope="session")
def checkov_runner(checkov_bin):
    """Create a CheckovRunner instance."""
    runner = CheckovRunner(checkov_bin=checkov_bin)
    yield runner


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    tmpdir = tempfile.mkdtemp(prefix="tf_perf_")
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def small_terraform_config():
    """Generate a small terraform config (5 resources)."""
    from utils.terraform_utils import generate_terraform_config

    return generate_terraform_config(resource_count=5)


@pytest.fixture
def medium_terraform_config():
    """Generate a medium terraform config (25 resources)."""
    from utils.terraform_utils import generate_terraform_config

    return generate_terraform_config(resource_count=25)


@pytest.fixture
def large_terraform_config():
    """Generate a large terraform config (100 resources)."""
    from utils.terraform_utils import generate_terraform_config

    return generate_terraform_config(resource_count=100)


@pytest.fixture
def rego_policy_dir():
    """Path to the rego policy directory."""
    return str(REGO_POLICY_DIR)


@pytest.fixture
def checkov_policy_dir():
    """Path to the checkov policy directory."""
    return str(CHECKOV_POLICY_DIR)


@pytest.fixture
def sample_opa_input():
    """Create a sample OPA input document."""
    return create_opa_input()


@pytest.fixture
def non_compliant_opa_input():
    """Create a non-compliant OPA input document."""
    return create_opa_input(
        resource_id="non-compliant-resource",
        environment="production",
        region="us-east-1",
        tags={},
        encryption={"at_rest": False, "in_transit": False},
        network={"segment": "public"},
        access={"mfa": False, "privilege": "admin"},
        backup={"enabled": False},
        monitoring={"enabled": False},
        logging={"enabled": False},
        certificate={"expiry_days": 5},
        license={"expiry_days": 5},
        support={"expiry_days": 5},
        security_assessment="",
        risk_assessment="",
        compliance_assessment="",
        audit_trail="",
        configuration_management="",
        asset_inventory="",
        vulnerability_management="",
        patch_management="",
        capacity_management="",
        performance_management="",
        availability_management="",
        service_level_agreement="",
        operational_level_agreement="",
        underpinning_contract="",
        service_catalog="",
        service_portfolio="",
        service_design_package="",
        service_transition_plan="",
        service_operation_plan="",
        continual_service_improvement_plan="",
        service_reporting="",
        service_measurement="",
        service_level_management="",
        service_continuity_management="",
        it_service_continuity_management="",
        information_security_management="",
        supplier_management="",
        relationship_management="",
        design_coordination="",
        service_asset_and_configuration_management="",
        release_and_deployment_management="",
        service_validation_and_testing="",
        knowledge_management="",
        incident_management="",
        problem_management="",
        event_management="",
        request_fulfillment="",
        access_management="",
        service_desk="",
        technical_management="",
        application_management="",
        it_operations_management="",
        facilities_management="",
        infrastructure_management="",
        network_management="",
        storage_management="",
        database_management="",
        middleware_management="",
        web_management="",
        identity_management="",
        entitlement_management="",
        role_management="",
        privilege_management="",
        policy_management="",
        compliance_management="",
        risk_management="",
        audit_management="",
        governance="",
    )
