# common.rego — shared helpers for Data Center Commander governance policies
package common

# --- Severity levels ---
severity_critical := "critical"
severity_high     := "high"
severity_medium   := "medium"
severity_low      := "low"

# --- Environment classification ---
is_production if { input.environment == "production" }
is_staging    if { input.environment == "staging" }
is_dev        if { input.environment == "dev" }

# --- Helper: check if a resource has a specific tag key ---
has_tag(key) if {
    input.tags[key] != null
}

# --- Helper: check if a tag value matches a pattern ---
tag_matches(key, pattern) if {
    has_tag(key)
    regex.match(pattern, input.tags[key])
}

# --- Helper: resource is in allowed region ---
in_allowed_regions if {
    allowed := {"us-east-1", "us-west-2", "eu-west-1", "eu-central-1"}
    allowed[input.region]
}

# --- Helper: encryption checks ---
encrypted_at_rest if { input.encryption.at_rest == true }
encrypted_in_transit if { input.encryption.in_transit == true }

# --- Helper: network segment checks ---
is_isolated_segment if { input.network.segment == "isolated" }
is_restricted_segment if { input.network.segment == "restricted" }
is_public_segment if { input.network.segment == "public" }

# --- Helper: access checks ---
mfa_enabled if { input.access.mfa == true }
least_privilege if { input.access.privilege == "least" }

# --- Helper: required tags ---
has_owner if { has_tag("owner") }
has_cost_center if { has_tag("cost_center") }
has_data_classification if { has_tag("data_classification") }
has_compliance_scope if { has_tag("compliance_scope") }

# --- Helper: operational checks ---
within_retention if { input.retention_days <= input.max_retention_days }
recently_reviewed if { input.last_review_days <= 90 }
has_backup if { input.backup.enabled == true }
has_monitoring if { input.monitoring.enabled == true }
has_logging if { input.logging.enabled == true }

# --- Helper: certificate / license / support validity ---
valid_certificate if { input.certificate.expiry_days > 30 }
valid_license if { input.license.expiry_days > 30 }
valid_support if { input.support.expiry_days > 30 }

# --- Helper: management records ---
valid_maintenance_window if { input.maintenance_window != "" }
valid_change_management if { input.change_management != "" }
valid_incident_response if { input.incident_response != "" }
valid_disaster_recovery if { input.disaster_recovery != "" }
valid_business_continuity if { input.business_continuity != "" }
valid_security_assessment if { input.security_assessment != "" }
valid_risk_assessment if { input.risk_assessment != "" }
valid_compliance_assessment if { input.compliance_assessment != "" }
valid_audit_trail if { input.audit_trail != "" }
valid_configuration_management if { input.configuration_management != "" }
valid_asset_inventory if { input.asset_inventory != "" }
valid_vulnerability_management if { input.vulnerability_management != "" }
valid_patch_management if { input.patch_management != "" }
valid_capacity_management if { input.capacity_management != "" }
valid_performance_management if { input.performance_management != "" }
valid_availability_management if { input.availability_management != "" }
valid_service_level_agreement if { input.service_level_agreement != "" }
valid_operational_level_agreement if { input.operational_level_agreement != "" }
valid_underpinning_contract if { input.underpinning_contract != "" }
valid_service_catalog if { input.service_catalog != "" }
valid_service_portfolio if { input.service_portfolio != "" }
valid_service_design_package if { input.service_design_package != "" }
valid_service_transition_plan if { input.service_transition_plan != "" }
valid_service_operation_plan if { input.service_operation_plan != "" }
valid_continual_service_improvement_plan if { input.continual_service_improvement_plan != "" }
valid_service_reporting if { input.service_reporting != "" }
valid_service_measurement if { input.service_measurement != "" }
valid_service_level_management if { input.service_level_management != "" }
valid_service_continuity_management if { input.service_continuity_management != "" }
valid_it_service_continuity_management if { input.it_service_continuity_management != "" }
valid_information_security_management if { input.information_security_management != "" }
valid_supplier_management if { input.supplier_management != "" }
valid_relationship_management if { input.relationship_management != "" }
valid_design_coordination if { input.design_coordination != "" }
valid_service_asset_and_configuration_management if { input.service_asset_and_configuration_management != "" }
valid_release_and_deployment_management if { input.release_and_deployment_management != "" }
valid_service_validation_and_testing if { input.service_validation_and_testing != "" }
valid_knowledge_management if { input.knowledge_management != "" }
valid_incident_management if { input.incident_management != "" }
valid_problem_management if { input.problem_management != "" }
valid_event_management if { input.event_management != "" }
valid_request_fulfillment if { input.request_fulfillment != "" }
valid_access_management if { input.access_management != "" }
valid_service_desk if { input.service_desk != "" }
valid_technical_management if { input.technical_management != "" }
valid_application_management if { input.application_management != "" }
valid_it_operations_management if { input.it_operations_management != "" }
valid_facilities_management if { input.facilities_management != "" }
valid_infrastructure_management if { input.infrastructure_management != "" }
valid_network_management if { input.network_management != "" }
valid_storage_management if { input.storage_management != "" }
valid_database_management if { input.database_management != "" }
valid_middleware_management if { input.middleware_management != "" }
valid_web_management if { input.web_management != "" }
valid_identity_management if { input.identity_management != "" }
valid_entitlement_management if { input.entitlement_management != "" }
valid_role_management if { input.role_management != "" }
valid_privilege_management if { input.privilege_management != "" }
valid_policy_management if { input.policy_management != "" }
valid_compliance_management if { input.compliance_management != "" }
valid_risk_management if { input.risk_management != "" }
valid_audit_management if { input.audit_management != "" }
valid_governance if { input.governance != "" }
