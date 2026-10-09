"""
OPA/Rego Policy Tests — Compliance
Tests for datacenter.compliance package.
"""

import json
import subprocess
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from helpers import run_opa, make_resource


class TestCompliance:
    """Tests for compliance policy."""

    def test_fully_compliant_resource_passes(self):
        """A resource with all compliance settings should produce no violations."""
        resource = make_resource()
        result = run_opa(resource, "datacenter.compliance")
        assert result.get("result", [{}])[0].get("expressions", [{}])[0].get("value", []) == []

    def test_production_missing_security_assessment_fails(self):
        """Production resource without security assessment should be denied."""
        resource = make_resource()
        resource["security_assessment"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("security assessment" in d for d in denies)

    def test_production_missing_risk_assessment_fails(self):
        """Production resource without risk assessment should be denied."""
        resource = make_resource()
        resource["risk_assessment"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("risk assessment" in d for d in denies)

    def test_production_missing_compliance_assessment_fails(self):
        """Production resource without compliance assessment should be denied."""
        resource = make_resource()
        resource["compliance_assessment"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("compliance assessment" in d for d in denies)

    def test_production_missing_audit_trail_fails(self):
        """Production resource without audit trail should be denied."""
        resource = make_resource()
        resource["audit_trail"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("audit trail" in d for d in denies)

    def test_production_missing_configuration_management_fails(self):
        """Production resource without configuration management should be denied."""
        resource = make_resource()
        resource["configuration_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("configuration management" in d for d in denies)

    def test_production_missing_asset_inventory_fails(self):
        """Production resource without asset inventory should be denied."""
        resource = make_resource()
        resource["asset_inventory"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("asset inventory" in d for d in denies)

    def test_production_missing_vulnerability_management_fails(self):
        """Production resource without vulnerability management should be denied."""
        resource = make_resource()
        resource["vulnerability_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("vulnerability management" in d for d in denies)

    def test_production_missing_patch_management_fails(self):
        """Production resource without patch management should be denied."""
        resource = make_resource()
        resource["patch_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("patch management" in d for d in denies)

    def test_production_missing_capacity_management_fails(self):
        """Production resource without capacity management should be denied."""
        resource = make_resource()
        resource["capacity_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("capacity management" in d for d in denies)

    def test_production_missing_performance_management_fails(self):
        """Production resource without performance management should be denied."""
        resource = make_resource()
        resource["performance_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("performance management" in d for d in denies)

    def test_production_missing_availability_management_fails(self):
        """Production resource without availability management should be denied."""
        resource = make_resource()
        resource["availability_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("availability management" in d for d in denies)

    def test_production_missing_service_level_agreement_fails(self):
        """Production resource without service level agreement should be denied."""
        resource = make_resource()
        resource["service_level_agreement"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service level agreement" in d for d in denies)

    def test_production_missing_operational_level_agreement_fails(self):
        """Production resource without operational level agreement should be denied."""
        resource = make_resource()
        resource["operational_level_agreement"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("operational level agreement" in d for d in denies)

    def test_production_missing_underpinning_contract_fails(self):
        """Production resource without underpinning contract should be denied."""
        resource = make_resource()
        resource["underpinning_contract"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("underpinning contract" in d for d in denies)

    def test_production_missing_service_catalog_fails(self):
        """Production resource without service catalog should be denied."""
        resource = make_resource()
        resource["service_catalog"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service catalog" in d for d in denies)

    def test_production_missing_service_portfolio_fails(self):
        """Production resource without service portfolio should be denied."""
        resource = make_resource()
        resource["service_portfolio"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service portfolio" in d for d in denies)

    def test_production_missing_service_design_package_fails(self):
        """Production resource without service design package should be denied."""
        resource = make_resource()
        resource["service_design_package"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service design package" in d for d in denies)

    def test_production_missing_service_transition_plan_fails(self):
        """Production resource without service transition plan should be denied."""
        resource = make_resource()
        resource["service_transition_plan"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service transition plan" in d for d in denies)

    def test_production_missing_service_operation_plan_fails(self):
        """Production resource without service operation plan should be denied."""
        resource = make_resource()
        resource["service_operation_plan"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service operation plan" in d for d in denies)

    def test_production_missing_continual_service_improvement_plan_fails(self):
        """Production resource without continual service improvement plan should be denied."""
        resource = make_resource()
        resource["continual_service_improvement_plan"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("continual service improvement plan" in d for d in denies)

    def test_production_missing_service_reporting_fails(self):
        """Production resource without service reporting should be denied."""
        resource = make_resource()
        resource["service_reporting"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service reporting" in d for d in denies)

    def test_production_missing_service_measurement_fails(self):
        """Production resource without service measurement should be denied."""
        resource = make_resource()
        resource["service_measurement"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service measurement" in d for d in denies)

    def test_production_missing_service_level_management_fails(self):
        """Production resource without service level management should be denied."""
        resource = make_resource()
        resource["service_level_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service level management" in d for d in denies)

    def test_production_missing_service_continuity_management_fails(self):
        """Production resource without service continuity management should be denied."""
        resource = make_resource()
        resource["service_continuity_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service continuity management" in d for d in denies)

    def test_production_missing_it_service_continuity_management_fails(self):
        """Production resource without IT service continuity management should be denied."""
        resource = make_resource()
        resource["it_service_continuity_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("IT service continuity management" in d for d in denies)

    def test_production_missing_information_security_management_fails(self):
        """Production resource without information security management should be denied."""
        resource = make_resource()
        resource["information_security_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("information security management" in d for d in denies)

    def test_production_missing_supplier_management_fails(self):
        """Production resource without supplier management should be denied."""
        resource = make_resource()
        resource["supplier_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("supplier management" in d for d in denies)

    def test_production_missing_relationship_management_fails(self):
        """Production resource without relationship management should be denied."""
        resource = make_resource()
        resource["relationship_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("relationship management" in d for d in denies)

    def test_production_missing_design_coordination_fails(self):
        """Production resource without design coordination should be denied."""
        resource = make_resource()
        resource["design_coordination"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("design coordination" in d for d in denies)

    def test_production_missing_service_asset_and_configuration_management_fails(self):
        """Production resource without service asset and configuration management should be denied."""
        resource = make_resource()
        resource["service_asset_and_configuration_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service asset and configuration management" in d for d in denies)

    def test_production_missing_release_and_deployment_management_fails(self):
        """Production resource without release and deployment management should be denied."""
        resource = make_resource()
        resource["release_and_deployment_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("release and deployment management" in d for d in denies)

    def test_production_missing_service_validation_and_testing_fails(self):
        """Production resource without service validation and testing should be denied."""
        resource = make_resource()
        resource["service_validation_and_testing"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service validation and testing" in d for d in denies)

    def test_production_missing_change_management_fails(self):
        """Production resource without change management should be denied."""
        resource = make_resource()
        resource["change_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("change management" in d for d in denies)

    def test_production_missing_knowledge_management_fails(self):
        """Production resource without knowledge management should be denied."""
        resource = make_resource()
        resource["knowledge_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("knowledge management" in d for d in denies)

    def test_production_missing_incident_management_fails(self):
        """Production resource without incident management should be denied."""
        resource = make_resource()
        resource["incident_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("incident management" in d for d in denies)

    def test_production_missing_problem_management_fails(self):
        """Production resource without problem management should be denied."""
        resource = make_resource()
        resource["problem_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("problem management" in d for d in denies)

    def test_production_missing_event_management_fails(self):
        """Production resource without event management should be denied."""
        resource = make_resource()
        resource["event_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("event management" in d for d in denies)

    def test_production_missing_request_fulfillment_fails(self):
        """Production resource without request fulfillment should be denied."""
        resource = make_resource()
        resource["request_fulfillment"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("request fulfillment" in d for d in denies)

    def test_production_missing_access_management_fails(self):
        """Production resource without access management should be denied."""
        resource = make_resource()
        resource["access_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("access management" in d for d in denies)

    def test_production_missing_service_desk_fails(self):
        """Production resource without service desk should be denied."""
        resource = make_resource()
        resource["service_desk"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service desk" in d for d in denies)

    def test_production_missing_technical_management_fails(self):
        """Production resource without technical management should be denied."""
        resource = make_resource()
        resource["technical_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("technical management" in d for d in denies)

    def test_production_missing_application_management_fails(self):
        """Production resource without application management should be denied."""
        resource = make_resource()
        resource["application_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("application management" in d for d in denies)

    def test_production_missing_it_operations_management_fails(self):
        """Production resource without IT operations management should be denied."""
        resource = make_resource()
        resource["it_operations_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("IT operations management" in d for d in denies)

    def test_production_missing_facilities_management_fails(self):
        """Production resource without facilities management should be denied."""
        resource = make_resource()
        resource["facilities_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("facilities management" in d for d in denies)

    def test_production_missing_infrastructure_management_fails(self):
        """Production resource without infrastructure management should be denied."""
        resource = make_resource()
        resource["infrastructure_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("infrastructure management" in d for d in denies)

    def test_production_missing_network_management_fails(self):
        """Production resource without network management should be denied."""
        resource = make_resource()
        resource["network_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("network management" in d for d in denies)

    def test_production_missing_storage_management_fails(self):
        """Production resource without storage management should be denied."""
        resource = make_resource()
        resource["storage_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("storage management" in d for d in denies)

    def test_production_missing_database_management_fails(self):
        """Production resource without database management should be denied."""
        resource = make_resource()
        resource["database_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("database management" in d for d in denies)

    def test_production_missing_middleware_management_fails(self):
        """Production resource without middleware management should be denied."""
        resource = make_resource()
        resource["middleware_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("middleware management" in d for d in denies)

    def test_production_missing_web_management_fails(self):
        """Production resource without web management should be denied."""
        resource = make_resource()
        resource["web_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("web management" in d for d in denies)

    def test_production_missing_identity_management_fails(self):
        """Production resource without identity management should be denied."""
        resource = make_resource()
        resource["identity_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("identity management" in d for d in denies)

    def test_production_missing_entitlement_management_fails(self):
        """Production resource without entitlement management should be denied."""
        resource = make_resource()
        resource["entitlement_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("entitlement management" in d for d in denies)

    def test_production_missing_role_management_fails(self):
        """Production resource without role management should be denied."""
        resource = make_resource()
        resource["role_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("role management" in d for d in denies)

    def test_production_missing_privilege_management_fails(self):
        """Production resource without privilege management should be denied."""
        resource = make_resource()
        resource["privilege_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("privilege management" in d for d in denies)

    def test_production_missing_policy_management_fails(self):
        """Production resource without policy management should be denied."""
        resource = make_resource()
        resource["policy_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("policy management" in d for d in denies)

    def test_production_missing_compliance_management_fails(self):
        """Production resource without compliance management should be denied."""
        resource = make_resource()
        resource["compliance_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("compliance management" in d for d in denies)

    def test_production_missing_risk_management_fails(self):
        """Production resource without risk management should be denied."""
        resource = make_resource()
        resource["risk_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("risk management" in d for d in denies)

    def test_production_missing_audit_management_fails(self):
        """Production resource without audit management should be denied."""
        resource = make_resource()
        resource["audit_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("audit management" in d for d in denies)

    def test_production_missing_governance_fails(self):
        """Production resource without governance should be denied."""
        resource = make_resource()
        resource["governance"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("governance" in d for d in denies)

    def test_disallowed_region_fails(self):
        """Resource in disallowed region should be denied."""
        resource = make_resource()
        resource["region"] = "ap-south-1"
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("disallowed region" in d for d in denies)

    def test_invalid_certificate_fails(self):
        """Resource with invalid certificate should be denied."""
        resource = make_resource()
        resource["certificate"]["expiry_days"] = 15
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("certificate" in d for d in denies)

    def test_invalid_license_fails(self):
        """Resource with invalid license should be denied."""
        resource = make_resource()
        resource["license"]["expiry_days"] = 15
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("license" in d for d in denies)

    def test_invalid_support_fails(self):
        """Resource with invalid support contract should be denied."""
        resource = make_resource()
        resource["support"]["expiry_days"] = 15
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("support" in d for d in denies)

    def test_missing_maintenance_window_fails(self):
        """Resource without maintenance window should be denied."""
        resource = make_resource()
        resource["maintenance_window"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("maintenance window" in d for d in denies)

    def test_missing_change_management_fails(self):
        """Resource without change management should be denied."""
        resource = make_resource()
        resource["change_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("change management" in d for d in denies)

    def test_missing_incident_response_fails(self):
        """Resource without incident response should be denied."""
        resource = make_resource()
        resource["incident_response"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("incident response" in d for d in denies)

    def test_missing_disaster_recovery_fails(self):
        """Resource without disaster recovery should be denied."""
        resource = make_resource()
        resource["disaster_recovery"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("disaster recovery" in d for d in denies)

    def test_missing_business_continuity_fails(self):
        """Resource without business continuity should be denied."""
        resource = make_resource()
        resource["business_continuity"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("business continuity" in d for d in denies)

    def test_missing_security_assessment_fails(self):
        """Resource without security assessment should be denied."""
        resource = make_resource()
        resource["security_assessment"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("security assessment" in d for d in denies)

    def test_missing_risk_assessment_fails(self):
        """Resource without risk assessment should be denied."""
        resource = make_resource()
        resource["risk_assessment"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("risk assessment" in d for d in denies)

    def test_missing_compliance_assessment_fails(self):
        """Resource without compliance assessment should be denied."""
        resource = make_resource()
        resource["compliance_assessment"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("compliance assessment" in d for d in denies)

    def test_missing_audit_trail_fails(self):
        """Resource without audit trail should be denied."""
        resource = make_resource()
        resource["audit_trail"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("audit trail" in d for d in denies)

    def test_missing_configuration_management_fails(self):
        """Resource without configuration management should be denied."""
        resource = make_resource()
        resource["configuration_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("configuration management" in d for d in denies)

    def test_missing_asset_inventory_fails(self):
        """Resource without asset inventory should be denied."""
        resource = make_resource()
        resource["asset_inventory"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("asset inventory" in d for d in denies)

    def test_missing_vulnerability_management_fails(self):
        """Resource without vulnerability management should be denied."""
        resource = make_resource()
        resource["vulnerability_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("vulnerability management" in d for d in denies)

    def test_missing_patch_management_fails(self):
        """Resource without patch management should be denied."""
        resource = make_resource()
        resource["patch_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("patch management" in d for d in denies)

    def test_missing_capacity_management_fails(self):
        """Resource without capacity management should be denied."""
        resource = make_resource()
        resource["capacity_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("capacity management" in d for d in denies)

    def test_missing_performance_management_fails(self):
        """Resource without performance management should be denied."""
        resource = make_resource()
        resource["performance_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("performance management" in d for d in denies)

    def test_missing_availability_management_fails(self):
        """Resource without availability management should be denied."""
        resource = make_resource()
        resource["availability_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("availability management" in d for d in denies)

    def test_missing_service_level_agreement_fails(self):
        """Resource without service level agreement should be denied."""
        resource = make_resource()
        resource["service_level_agreement"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service level agreement" in d for d in denies)

    def test_missing_operational_level_agreement_fails(self):
        """Resource without operational level agreement should be denied."""
        resource = make_resource()
        resource["operational_level_agreement"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("operational level agreement" in d for d in denies)

    def test_missing_underpinning_contract_fails(self):
        """Resource without underpinning contract should be denied."""
        resource = make_resource()
        resource["underpinning_contract"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("underpinning contract" in d for d in denies)

    def test_missing_service_catalog_fails(self):
        """Resource without service catalog should be denied."""
        resource = make_resource()
        resource["service_catalog"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service catalog" in d for d in denies)

    def test_missing_service_portfolio_fails(self):
        """Resource without service portfolio should be denied."""
        resource = make_resource()
        resource["service_portfolio"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service portfolio" in d for d in denies)

    def test_missing_service_design_package_fails(self):
        """Resource without service design package should be denied."""
        resource = make_resource()
        resource["service_design_package"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service design package" in d for d in denies)

    def test_missing_service_transition_plan_fails(self):
        """Resource without service transition plan should be denied."""
        resource = make_resource()
        resource["service_transition_plan"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service transition plan" in d for d in denies)

    def test_missing_service_operation_plan_fails(self):
        """Resource without service operation plan should be denied."""
        resource = make_resource()
        resource["service_operation_plan"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service operation plan" in d for d in denies)

    def test_missing_continual_service_improvement_plan_fails(self):
        """Resource without continual service improvement plan should be denied."""
        resource = make_resource()
        resource["continual_service_improvement_plan"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("continual service improvement plan" in d for d in denies)

    def test_missing_service_reporting_fails(self):
        """Resource without service reporting should be denied."""
        resource = make_resource()
        resource["service_reporting"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service reporting" in d for d in denies)

    def test_missing_service_measurement_fails(self):
        """Resource without service measurement should be denied."""
        resource = make_resource()
        resource["service_measurement"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service measurement" in d for d in denies)

    def test_missing_service_level_management_fails(self):
        """Resource without service level management should be denied."""
        resource = make_resource()
        resource["service_level_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service level management" in d for d in denies)

    def test_missing_service_continuity_management_fails(self):
        """Resource without service continuity management should be denied."""
        resource = make_resource()
        resource["service_continuity_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service continuity management" in d for d in denies)

    def test_missing_it_service_continuity_management_fails(self):
        """Resource without IT service continuity management should be denied."""
        resource = make_resource()
        resource["it_service_continuity_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("IT service continuity management" in d for d in denies)

    def test_missing_information_security_management_fails(self):
        """Resource without information security management should be denied."""
        resource = make_resource()
        resource["information_security_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("information security management" in d for d in denies)

    def test_missing_supplier_management_fails(self):
        """Resource without supplier management should be denied."""
        resource = make_resource()
        resource["supplier_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("supplier management" in d for d in denies)

    def test_missing_relationship_management_fails(self):
        """Resource without relationship management should be denied."""
        resource = make_resource()
        resource["relationship_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("relationship management" in d for d in denies)

    def test_missing_design_coordination_fails(self):
        """Resource without design coordination should be denied."""
        resource = make_resource()
        resource["design_coordination"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("design coordination" in d for d in denies)

    def test_missing_service_asset_and_configuration_management_fails(self):
        """Resource without service asset and configuration management should be denied."""
        resource = make_resource()
        resource["service_asset_and_configuration_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service asset and configuration management" in d for d in denies)

    def test_missing_release_and_deployment_management_fails(self):
        """Resource without release and deployment management should be denied."""
        resource = make_resource()
        resource["release_and_deployment_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("release and deployment management" in d for d in denies)

    def test_missing_service_validation_and_testing_fails(self):
        """Resource without service validation and testing should be denied."""
        resource = make_resource()
        resource["service_validation_and_testing"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service validation and testing" in d for d in denies)

    def test_missing_knowledge_management_fails(self):
        """Resource without knowledge management should be denied."""
        resource = make_resource()
        resource["knowledge_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("knowledge management" in d for d in denies)

    def test_missing_incident_management_fails(self):
        """Resource without incident management should be denied."""
        resource = make_resource()
        resource["incident_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("incident management" in d for d in denies)

    def test_missing_problem_management_fails(self):
        """Resource without problem management should be denied."""
        resource = make_resource()
        resource["problem_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("problem management" in d for d in denies)

    def test_missing_event_management_fails(self):
        """Resource without event management should be denied."""
        resource = make_resource()
        resource["event_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("event management" in d for d in denies)

    def test_missing_request_fulfillment_fails(self):
        """Resource without request fulfillment should be denied."""
        resource = make_resource()
        resource["request_fulfillment"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("request fulfillment" in d for d in denies)

    def test_missing_access_management_fails(self):
        """Resource without access management should be denied."""
        resource = make_resource()
        resource["access_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("access management" in d for d in denies)

    def test_missing_service_desk_fails(self):
        """Resource without service desk should be denied."""
        resource = make_resource()
        resource["service_desk"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service desk" in d for d in denies)

    def test_missing_technical_management_fails(self):
        """Resource without technical management should be denied."""
        resource = make_resource()
        resource["technical_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("technical management" in d for d in denies)

    def test_missing_application_management_fails(self):
        """Resource without application management should be denied."""
        resource = make_resource()
        resource["application_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("application management" in d for d in denies)

    def test_missing_it_operations_management_fails(self):
        """Resource without IT operations management should be denied."""
        resource = make_resource()
        resource["it_operations_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("IT operations management" in d for d in denies)

    def test_missing_facilities_management_fails(self):
        """Resource without facilities management should be denied."""
        resource = make_resource()
        resource["facilities_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("facilities management" in d for d in denies)

    def test_missing_infrastructure_management_fails(self):
        """Resource without infrastructure management should be denied."""
        resource = make_resource()
        resource["infrastructure_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("infrastructure management" in d for d in denies)

    def test_missing_network_management_fails(self):
        """Resource without network management should be denied."""
        resource = make_resource()
        resource["network_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("network management" in d for d in denies)

    def test_missing_storage_management_fails(self):
        """Resource without storage management should be denied."""
        resource = make_resource()
        resource["storage_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("storage management" in d for d in denies)

    def test_missing_database_management_fails(self):
        """Resource without database management should be denied."""
        resource = make_resource()
        resource["database_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("database management" in d for d in denies)

    def test_missing_middleware_management_fails(self):
        """Resource without middleware management should be denied."""
        resource = make_resource()
        resource["middleware_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("middleware management" in d for d in denies)

    def test_missing_web_management_fails(self):
        """Resource without web management should be denied."""
        resource = make_resource()
        resource["web_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("web management" in d for d in denies)

    def test_missing_identity_management_fails(self):
        """Resource without identity management should be denied."""
        resource = make_resource()
        resource["identity_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("identity management" in d for d in denies)

    def test_missing_entitlement_management_fails(self):
        """Resource without entitlement management should be denied."""
        resource = make_resource()
        resource["entitlement_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("entitlement management" in d for d in denies)

    def test_missing_role_management_fails(self):
        """Resource without role management should be denied."""
        resource = make_resource()
        resource["role_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("role management" in d for d in denies)

    def test_missing_privilege_management_fails(self):
        """Resource without privilege management should be denied."""
        resource = make_resource()
        resource["privilege_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("privilege management" in d for d in denies)

    def test_missing_policy_management_fails(self):
        """Resource without policy management should be denied."""
        resource = make_resource()
        resource["policy_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("policy management" in d for d in denies)

    def test_missing_compliance_management_fails(self):
        """Resource without compliance management should be denied."""
        resource = make_resource()
        resource["compliance_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("compliance management" in d for d in denies)

    def test_missing_risk_management_fails(self):
        """Resource without risk management should be denied."""
        resource = make_resource()
        resource["risk_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("risk management" in d for d in denies)

    def test_missing_audit_management_fails(self):
        """Resource without audit management should be denied."""
        resource = make_resource()
        resource["audit_management"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("audit management" in d for d in denies)

    def test_missing_governance_fails(self):
        """Resource without governance should be denied."""
        resource = make_resource()
        resource["governance"] = ""
        result = run_opa(resource, "datacenter.compliance")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("governance" in d for d in denies)
