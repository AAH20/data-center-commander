"""
OPA/Rego Policy Tests — Resource Tagging
Tests for datacenter.resource_tagging package.
"""

import json
import subprocess
import pytest
import os
import sys

# Add the opa directory to the path for helpers
sys.path.insert(0, os.path.dirname(__file__))
from helpers import run_opa, make_resource


class TestResourceTaggingCompliance:
    """Tests for resource tagging policy compliance."""

    def test_fully_compliant_resource_passes(self):
        """A resource with all required tags should produce no violations."""
        resource = make_resource()
        result = run_opa(resource)
        # Result should be empty (no deny messages)
        assert result.get("result", [{}])[0].get("expressions", [{}])[0].get("value", []) == []

    def test_missing_owner_tag_fails(self):
        """Resource without owner tag should be denied."""
        resource = make_resource()
        del resource["tags"]["owner"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert len(denies) > 0
        assert any("owner" in d for d in denies)

    def test_missing_cost_center_tag_fails(self):
        """Resource without cost_center tag should be denied."""
        resource = make_resource()
        del resource["tags"]["cost_center"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("cost_center" in d for d in denies)

    def test_missing_data_classification_tag_fails(self):
        """Resource without data_classification tag should be denied."""
        resource = make_resource()
        del resource["tags"]["data_classification"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("data_classification" in d for d in denies)

    def test_missing_compliance_scope_tag_fails(self):
        """Resource without compliance_scope tag should be denied."""
        resource = make_resource()
        del resource["tags"]["compliance_scope"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("compliance_scope" in d for d in denies)

    def test_missing_environment_tag_fails(self):
        """Resource without environment tag should be denied."""
        resource = make_resource()
        del resource["tags"]["environment"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("environment" in d for d in denies)

    def test_missing_project_tag_fails(self):
        """Resource without project tag should be denied."""
        resource = make_resource()
        del resource["tags"]["project"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("project" in d for d in denies)

    def test_missing_team_tag_fails(self):
        """Resource without team tag should be denied."""
        resource = make_resource()
        del resource["tags"]["team"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("team" in d for d in denies)

    def test_missing_service_tag_fails(self):
        """Resource without service tag should be denied."""
        resource = make_resource()
        del resource["tags"]["service"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service" in d for d in denies)

    def test_missing_version_tag_fails(self):
        """Resource without version tag should be denied."""
        resource = make_resource()
        del resource["tags"]["version"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("version" in d for d in denies)

    def test_missing_created_date_tag_fails(self):
        """Resource without created_date tag should be denied."""
        resource = make_resource()
        del resource["tags"]["created_date"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("created_date" in d for d in denies)

    def test_missing_last_reviewed_tag_fails(self):
        """Resource without last_reviewed tag should be denied."""
        resource = make_resource()
        del resource["tags"]["last_reviewed"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("last_reviewed" in d for d in denies)

    def test_missing_backup_policy_tag_fails(self):
        """Resource without backup_policy tag should be denied."""
        resource = make_resource()
        del resource["tags"]["backup_policy"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("backup_policy" in d for d in denies)

    def test_missing_retention_policy_tag_fails(self):
        """Resource without retention_policy tag should be denied."""
        resource = make_resource()
        del resource["tags"]["retention_policy"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("retention_policy" in d for d in denies)

    def test_missing_disaster_recovery_tag_fails(self):
        """Resource without disaster_recovery tag should be denied."""
        resource = make_resource()
        del resource["tags"]["disaster_recovery"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("disaster_recovery" in d for d in denies)

    def test_missing_business_continuity_tag_fails(self):
        """Resource without business_continuity tag should be denied."""
        resource = make_resource()
        del resource["tags"]["business_continuity"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("business_continuity" in d for d in denies)

    def test_missing_security_assessment_tag_fails(self):
        """Resource without security_assessment tag should be denied."""
        resource = make_resource()
        del resource["tags"]["security_assessment"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("security_assessment" in d for d in denies)

    def test_missing_risk_assessment_tag_fails(self):
        """Resource without risk_assessment tag should be denied."""
        resource = make_resource()
        del resource["tags"]["risk_assessment"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("risk_assessment" in d for d in denies)

    def test_missing_compliance_assessment_tag_fails(self):
        """Resource without compliance_assessment tag should be denied."""
        resource = make_resource()
        del resource["tags"]["compliance_assessment"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("compliance_assessment" in d for d in denies)

    def test_missing_audit_trail_tag_fails(self):
        """Resource without audit_trail tag should be denied."""
        resource = make_resource()
        del resource["tags"]["audit_trail"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("audit_trail" in d for d in denies)

    def test_missing_configuration_management_tag_fails(self):
        """Resource without configuration_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["configuration_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("configuration_management" in d for d in denies)

    def test_missing_asset_inventory_tag_fails(self):
        """Resource without asset_inventory tag should be denied."""
        resource = make_resource()
        del resource["tags"]["asset_inventory"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("asset_inventory" in d for d in denies)

    def test_missing_vulnerability_management_tag_fails(self):
        """Resource without vulnerability_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["vulnerability_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("vulnerability_management" in d for d in denies)

    def test_missing_patch_management_tag_fails(self):
        """Resource without patch_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["patch_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("patch_management" in d for d in denies)

    def test_missing_capacity_management_tag_fails(self):
        """Resource without capacity_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["capacity_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("capacity_management" in d for d in denies)

    def test_missing_performance_management_tag_fails(self):
        """Resource without performance_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["performance_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("performance_management" in d for d in denies)

    def test_missing_availability_management_tag_fails(self):
        """Resource without availability_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["availability_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("availability_management" in d for d in denies)

    def test_missing_service_level_agreement_tag_fails(self):
        """Resource without service_level_agreement tag should be denied."""
        resource = make_resource()
        del resource["tags"]["service_level_agreement"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service_level_agreement" in d for d in denies)

    def test_missing_operational_level_agreement_tag_fails(self):
        """Resource without operational_level_agreement tag should be denied."""
        resource = make_resource()
        del resource["tags"]["operational_level_agreement"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("operational_level_agreement" in d for d in denies)

    def test_missing_underpinning_contract_tag_fails(self):
        """Resource without underpinning_contract tag should be denied."""
        resource = make_resource()
        del resource["tags"]["underpinning_contract"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("underpinning_contract" in d for d in denies)

    def test_missing_service_catalog_tag_fails(self):
        """Resource without service_catalog tag should be denied."""
        resource = make_resource()
        del resource["tags"]["service_catalog"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service_catalog" in d for d in denies)

    def test_missing_service_portfolio_tag_fails(self):
        """Resource without service_portfolio tag should be denied."""
        resource = make_resource()
        del resource["tags"]["service_portfolio"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service_portfolio" in d for d in denies)

    def test_missing_service_design_package_tag_fails(self):
        """Resource without service_design_package tag should be denied."""
        resource = make_resource()
        del resource["tags"]["service_design_package"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service_design_package" in d for d in denies)

    def test_missing_service_transition_plan_tag_fails(self):
        """Resource without service_transition_plan tag should be denied."""
        resource = make_resource()
        del resource["tags"]["service_transition_plan"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service_transition_plan" in d for d in denies)

    def test_missing_service_operation_plan_tag_fails(self):
        """Resource without service_operation_plan tag should be denied."""
        resource = make_resource()
        del resource["tags"]["service_operation_plan"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service_operation_plan" in d for d in denies)

    def test_missing_continual_service_improvement_plan_tag_fails(self):
        """Resource without continual_service_improvement_plan tag should be denied."""
        resource = make_resource()
        del resource["tags"]["continual_service_improvement_plan"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("continual_service_improvement_plan" in d for d in denies)

    def test_missing_service_reporting_tag_fails(self):
        """Resource without service_reporting tag should be denied."""
        resource = make_resource()
        del resource["tags"]["service_reporting"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service_reporting" in d for d in denies)

    def test_missing_service_measurement_tag_fails(self):
        """Resource without service_measurement tag should be denied."""
        resource = make_resource()
        del resource["tags"]["service_measurement"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service_measurement" in d for d in denies)

    def test_missing_service_level_management_tag_fails(self):
        """Resource without service_level_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["service_level_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service_level_management" in d for d in denies)

    def test_missing_service_continuity_management_tag_fails(self):
        """Resource without service_continuity_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["service_continuity_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service_continuity_management" in d for d in denies)

    def test_missing_it_service_continuity_management_tag_fails(self):
        """Resource without it_service_continuity_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["it_service_continuity_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("it_service_continuity_management" in d for d in denies)

    def test_missing_information_security_management_tag_fails(self):
        """Resource without information_security_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["information_security_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("information_security_management" in d for d in denies)

    def test_missing_supplier_management_tag_fails(self):
        """Resource without supplier_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["supplier_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("supplier_management" in d for d in denies)

    def test_missing_relationship_management_tag_fails(self):
        """Resource without relationship_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["relationship_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("relationship_management" in d for d in denies)

    def test_missing_design_coordination_tag_fails(self):
        """Resource without design_coordination tag should be denied."""
        resource = make_resource()
        del resource["tags"]["design_coordination"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("design_coordination" in d for d in denies)

    def test_missing_service_asset_and_configuration_management_tag_fails(self):
        """Resource without service_asset_and_configuration_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["service_asset_and_configuration_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service_asset_and_configuration_management" in d for d in denies)

    def test_missing_release_and_deployment_management_tag_fails(self):
        """Resource without release_and_deployment_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["release_and_deployment_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("release_and_deployment_management" in d for d in denies)

    def test_missing_service_validation_and_testing_tag_fails(self):
        """Resource without service_validation_and_testing tag should be denied."""
        resource = make_resource()
        del resource["tags"]["service_validation_and_testing"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service_validation_and_testing" in d for d in denies)

    def test_missing_change_management_tag_fails(self):
        """Resource without change_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["change_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("change_management" in d for d in denies)

    def test_missing_knowledge_management_tag_fails(self):
        """Resource without knowledge_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["knowledge_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("knowledge_management" in d for d in denies)

    def test_missing_incident_management_tag_fails(self):
        """Resource without incident_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["incident_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("incident_management" in d for d in denies)

    def test_missing_problem_management_tag_fails(self):
        """Resource without problem_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["problem_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("problem_management" in d for d in denies)

    def test_missing_event_management_tag_fails(self):
        """Resource without event_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["event_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("event_management" in d for d in denies)

    def test_missing_request_fulfillment_tag_fails(self):
        """Resource without request_fulfillment tag should be denied."""
        resource = make_resource()
        del resource["tags"]["request_fulfillment"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("request_fulfillment" in d for d in denies)

    def test_missing_access_management_tag_fails(self):
        """Resource without access_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["access_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("access_management" in d for d in denies)

    def test_missing_service_desk_tag_fails(self):
        """Resource without service_desk tag should be denied."""
        resource = make_resource()
        del resource["tags"]["service_desk"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service_desk" in d for d in denies)

    def test_missing_technical_management_tag_fails(self):
        """Resource without technical_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["technical_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("technical_management" in d for d in denies)

    def test_missing_application_management_tag_fails(self):
        """Resource without application_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["application_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("application_management" in d for d in denies)

    def test_missing_it_operations_management_tag_fails(self):
        """Resource without it_operations_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["it_operations_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("it_operations_management" in d for d in denies)

    def test_missing_facilities_management_tag_fails(self):
        """Resource without facilities_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["facilities_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("facilities_management" in d for d in denies)

    def test_missing_infrastructure_management_tag_fails(self):
        """Resource without infrastructure_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["infrastructure_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("infrastructure_management" in d for d in denies)

    def test_missing_network_management_tag_fails(self):
        """Resource without network_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["network_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("network_management" in d for d in denies)

    def test_missing_storage_management_tag_fails(self):
        """Resource without storage_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["storage_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("storage_management" in d for d in denies)

    def test_missing_database_management_tag_fails(self):
        """Resource without database_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["database_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("database_management" in d for d in denies)

    def test_missing_middleware_management_tag_fails(self):
        """Resource without middleware_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["middleware_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("middleware_management" in d for d in denies)

    def test_missing_web_management_tag_fails(self):
        """Resource without web_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["web_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("web_management" in d for d in denies)

    def test_missing_identity_management_tag_fails(self):
        """Resource without identity_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["identity_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("identity_management" in d for d in denies)

    def test_missing_entitlement_management_tag_fails(self):
        """Resource without entitlement_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["entitlement_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("entitlement_management" in d for d in denies)

    def test_missing_role_management_tag_fails(self):
        """Resource without role_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["role_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("role_management" in d for d in denies)

    def test_missing_privilege_management_tag_fails(self):
        """Resource without privilege_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["privilege_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("privilege_management" in d for d in denies)

    def test_missing_policy_management_tag_fails(self):
        """Resource without policy_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["policy_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("policy_management" in d for d in denies)

    def test_missing_compliance_management_tag_fails(self):
        """Resource without compliance_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["compliance_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("compliance_management" in d for d in denies)

    def test_missing_risk_management_tag_fails(self):
        """Resource without risk_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["risk_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("risk_management" in d for d in denies)

    def test_missing_audit_management_tag_fails(self):
        """Resource without audit_management tag should be denied."""
        resource = make_resource()
        del resource["tags"]["audit_management"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("audit_management" in d for d in denies)

    def test_missing_governance_tag_fails(self):
        """Resource without governance tag should be denied."""
        resource = make_resource()
        del resource["tags"]["governance"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("governance" in d for d in denies)

    def test_multiple_missing_tags_produces_multiple_violations(self):
        """Resource missing multiple tags should produce multiple violations."""
        resource = make_resource()
        del resource["tags"]["owner"]
        del resource["tags"]["cost_center"]
        del resource["tags"]["data_classification"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert len(denies) >= 3

    def test_empty_tags_fails(self):
        """Resource with empty tags should be denied."""
        resource = make_resource()
        resource["tags"] = {}
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert len(denies) > 0

    def test_no_tags_fails(self):
        """Resource with no tags key should be denied."""
        resource = make_resource()
        del resource["tags"]
        result = run_opa(resource)
        denies = result["result"][0]["expressions"][0]["value"]
        assert len(denies) > 0
