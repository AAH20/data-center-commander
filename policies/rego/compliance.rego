# compliance.rego — Compliance governance for Data Center Commander
package datacenter.compliance

import data.common

# --- Rule: Production resources must have a valid security assessment ---
deny contains msg if {
    common.is_production
    not common.valid_security_assessment
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid security assessment", [input.resource_id])
}

# --- Rule: Production resources must have a valid risk assessment ---
deny contains msg if {
    common.is_production
    not common.valid_risk_assessment
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid risk assessment", [input.resource_id])
}

# --- Rule: Production resources must have a valid compliance assessment ---
deny contains msg if {
    common.is_production
    not common.valid_compliance_assessment
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid compliance assessment", [input.resource_id])
}

# --- Rule: Production resources must have a valid audit trail ---
deny contains msg if {
    common.is_production
    not common.valid_audit_trail
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid audit trail", [input.resource_id])
}

# --- Rule: Production resources must have a valid configuration management record ---
deny contains msg if {
    common.is_production
    not common.valid_configuration_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid configuration management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid asset inventory record ---
deny contains msg if {
    common.is_production
    not common.valid_asset_inventory
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid asset inventory record", [input.resource_id])
}

# --- Rule: Production resources must have a valid vulnerability management record ---
deny contains msg if {
    common.is_production
    not common.valid_vulnerability_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid vulnerability management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid patch management record ---
deny contains msg if {
    common.is_production
    not common.valid_patch_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid patch management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid capacity management record ---
deny contains msg if {
    common.is_production
    not common.valid_capacity_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid capacity management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid performance management record ---
deny contains msg if {
    common.is_production
    not common.valid_performance_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid performance management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid availability management record ---
deny contains msg if {
    common.is_production
    not common.valid_availability_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid availability management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid service level agreement ---
deny contains msg if {
    common.is_production
    not common.valid_service_level_agreement
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid service level agreement", [input.resource_id])
}

# --- Rule: Production resources must have a valid operational level agreement ---
deny contains msg if {
    common.is_production
    not common.valid_operational_level_agreement
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid operational level agreement", [input.resource_id])
}

# --- Rule: Production resources must have a valid underpinning contract ---
deny contains msg if {
    common.is_production
    not common.valid_underpinning_contract
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid underpinning contract", [input.resource_id])
}

# --- Rule: Production resources must have a valid service catalog entry ---
deny contains msg if {
    common.is_production
    not common.valid_service_catalog
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid service catalog entry", [input.resource_id])
}

# --- Rule: Production resources must have a valid service portfolio entry ---
deny contains msg if {
    common.is_production
    not common.valid_service_portfolio
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid service portfolio entry", [input.resource_id])
}

# --- Rule: Production resources must have a valid service design package ---
deny contains msg if {
    common.is_production
    not common.valid_service_design_package
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid service design package", [input.resource_id])
}

# --- Rule: Production resources must have a valid service transition plan ---
deny contains msg if {
    common.is_production
    not common.valid_service_transition_plan
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid service transition plan", [input.resource_id])
}

# --- Rule: Production resources must have a valid service operation plan ---
deny contains msg if {
    common.is_production
    not common.valid_service_operation_plan
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid service operation plan", [input.resource_id])
}

# --- Rule: Production resources must have a valid continual service improvement plan ---
deny contains msg if {
    common.is_production
    not common.valid_continual_service_improvement_plan
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid continual service improvement plan", [input.resource_id])
}

# --- Rule: Production resources must have a valid service reporting record ---
deny contains msg if {
    common.is_production
    not common.valid_service_reporting
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid service reporting record", [input.resource_id])
}

# --- Rule: Production resources must have a valid service measurement record ---
deny contains msg if {
    common.is_production
    not common.valid_service_measurement
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid service measurement record", [input.resource_id])
}

# --- Rule: Production resources must have a valid service level management record ---
deny contains msg if {
    common.is_production
    not common.valid_service_level_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid service level management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid service continuity management record ---
deny contains msg if {
    common.is_production
    not common.valid_service_continuity_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid service continuity management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid IT service continuity management record ---
deny contains msg if {
    common.is_production
    not common.valid_it_service_continuity_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid IT service continuity management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid information security management record ---
deny contains msg if {
    common.is_production
    not common.valid_information_security_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid information security management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid supplier management record ---
deny contains msg if {
    common.is_production
    not common.valid_supplier_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid supplier management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid relationship management record ---
deny contains msg if {
    common.is_production
    not common.valid_relationship_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid relationship management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid design coordination record ---
deny contains msg if {
    common.is_production
    not common.valid_design_coordination
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid design coordination record", [input.resource_id])
}

# --- Rule: Production resources must have a valid service asset and configuration management record ---
deny contains msg if {
    common.is_production
    not common.valid_service_asset_and_configuration_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid service asset and configuration management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid release and deployment management record ---
deny contains msg if {
    common.is_production
    not common.valid_release_and_deployment_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid release and deployment management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid service validation and testing record ---
deny contains msg if {
    common.is_production
    not common.valid_service_validation_and_testing
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid service validation and testing record", [input.resource_id])
}

# --- Rule: Production resources must have a valid change management record ---
deny contains msg if {
    common.is_production
    not common.valid_change_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid change management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid knowledge management record ---
deny contains msg if {
    common.is_production
    not common.valid_knowledge_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid knowledge management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid incident management record ---
deny contains msg if {
    common.is_production
    not common.valid_incident_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid incident management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid problem management record ---
deny contains msg if {
    common.is_production
    not common.valid_problem_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid problem management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid event management record ---
deny contains msg if {
    common.is_production
    not common.valid_event_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid event management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid request fulfillment record ---
deny contains msg if {
    common.is_production
    not common.valid_request_fulfillment
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid request fulfillment record", [input.resource_id])
}

# --- Rule: Production resources must have a valid access management record ---
deny contains msg if {
    common.is_production
    not common.valid_access_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid access management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid service desk record ---
deny contains msg if {
    common.is_production
    not common.valid_service_desk
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid service desk record", [input.resource_id])
}

# --- Rule: Production resources must have a valid technical management record ---
deny contains msg if {
    common.is_production
    not common.valid_technical_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid technical management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid application management record ---
deny contains msg if {
    common.is_production
    not common.valid_application_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid application management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid IT operations management record ---
deny contains msg if {
    common.is_production
    not common.valid_it_operations_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid IT operations management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid facilities management record ---
deny contains msg if {
    common.is_production
    not common.valid_facilities_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid facilities management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid infrastructure management record ---
deny contains msg if {
    common.is_production
    not common.valid_infrastructure_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid infrastructure management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid network management record ---
deny contains msg if {
    common.is_production
    not common.valid_network_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid network management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid storage management record ---
deny contains msg if {
    common.is_production
    not common.valid_storage_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid storage management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid database management record ---
deny contains msg if {
    common.is_production
    not common.valid_database_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid database management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid middleware management record ---
deny contains msg if {
    common.is_production
    not common.valid_middleware_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid middleware management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid web management record ---
deny contains msg if {
    common.is_production
    not common.valid_web_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid web management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid identity management record ---
deny contains msg if {
    common.is_production
    not common.valid_identity_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid identity management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid entitlement management record ---
deny contains msg if {
    common.is_production
    not common.valid_entitlement_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid entitlement management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid role management record ---
deny contains msg if {
    common.is_production
    not common.valid_role_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid role management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid privilege management record ---
deny contains msg if {
    common.is_production
    not common.valid_privilege_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid privilege management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid policy management record ---
deny contains msg if {
    common.is_production
    not common.valid_policy_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid policy management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid compliance management record ---
deny contains msg if {
    common.is_production
    not common.valid_compliance_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid compliance management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid risk management record ---
deny contains msg if {
    common.is_production
    not common.valid_risk_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid risk management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid audit management record ---
deny contains msg if {
    common.is_production
    not common.valid_audit_management
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid audit management record", [input.resource_id])
}

# --- Rule: Production resources must have a valid governance record ---
deny contains msg if {
    common.is_production
    not common.valid_governance
    msg := sprintf("CRITICAL: Production resource '%s' must have a valid governance record", [input.resource_id])
}

# --- Rule: Resources must be in allowed regions ---
deny contains msg if {
    not common.in_allowed_regions
    msg := sprintf("HIGH: Resource '%s' is in disallowed region '%s'", [input.resource_id, input.region])
}

# --- Rule: Resources must have a valid certificate ---
deny contains msg if {
    not common.valid_certificate
    msg := sprintf("HIGH: Resource '%s' has an invalid or expiring certificate", [input.resource_id])
}

# --- Rule: Resources must have a valid license ---
deny contains msg if {
    not common.valid_license
    msg := sprintf("HIGH: Resource '%s' has an invalid or expiring license", [input.resource_id])
}

# --- Rule: Resources must have a valid support contract ---
deny contains msg if {
    not common.valid_support
    msg := sprintf("MEDIUM: Resource '%s' has an invalid or expiring support contract", [input.resource_id])
}

# --- Rule: Resources must have a valid maintenance window ---
deny contains msg if {
    not common.valid_maintenance_window
    msg := sprintf("MEDIUM: Resource '%s' must have a valid maintenance window", [input.resource_id])
}

# --- Rule: Resources must have a valid change management record ---
deny contains msg if {
    not common.valid_change_management
    msg := sprintf("HIGH: Resource '%s' must have a valid change management record", [input.resource_id])
}

# --- Rule: Resources must have a valid incident response plan ---
deny contains msg if {
    not common.valid_incident_response
    msg := sprintf("HIGH: Resource '%s' must have a valid incident response plan", [input.resource_id])
}

# --- Rule: Resources must have a valid disaster recovery plan ---
deny contains msg if {
    not common.valid_disaster_recovery
    msg := sprintf("HIGH: Resource '%s' must have a valid disaster recovery plan", [input.resource_id])
}

# --- Rule: Resources must have a valid business continuity plan ---
deny contains msg if {
    not common.valid_business_continuity
    msg := sprintf("HIGH: Resource '%s' must have a valid business continuity plan", [input.resource_id])
}

# --- Rule: Resources must have a valid security assessment ---
deny contains msg if {
    not common.valid_security_assessment
    msg := sprintf("HIGH: Resource '%s' must have a valid security assessment", [input.resource_id])
}

# --- Rule: Resources must have a valid risk assessment ---
deny contains msg if {
    not common.valid_risk_assessment
    msg := sprintf("HIGH: Resource '%s' must have a valid risk assessment", [input.resource_id])
}

# --- Rule: Resources must have a valid compliance assessment ---
deny contains msg if {
    not common.valid_compliance_assessment
    msg := sprintf("HIGH: Resource '%s' must have a valid compliance assessment", [input.resource_id])
}

# --- Rule: Resources must have a valid audit trail ---
deny contains msg if {
    not common.valid_audit_trail
    msg := sprintf("HIGH: Resource '%s' must have a valid audit trail", [input.resource_id])
}

# --- Rule: Resources must have a valid configuration management record ---
deny contains msg if {
    not common.valid_configuration_management
    msg := sprintf("HIGH: Resource '%s' must have a valid configuration management record", [input.resource_id])
}

# --- Rule: Resources must have a valid asset inventory record ---
deny contains msg if {
    not common.valid_asset_inventory
    msg := sprintf("HIGH: Resource '%s' must have a valid asset inventory record", [input.resource_id])
}

# --- Rule: Resources must have a valid vulnerability management record ---
deny contains msg if {
    not common.valid_vulnerability_management
    msg := sprintf("HIGH: Resource '%s' must have a valid vulnerability management record", [input.resource_id])
}

# --- Rule: Resources must have a valid patch management record ---
deny contains msg if {
    not common.valid_patch_management
    msg := sprintf("HIGH: Resource '%s' must have a valid patch management record", [input.resource_id])
}

# --- Rule: Resources must have a valid capacity management record ---
deny contains msg if {
    not common.valid_capacity_management
    msg := sprintf("HIGH: Resource '%s' must have a valid capacity management record", [input.resource_id])
}

# --- Rule: Resources must have a valid performance management record ---
deny contains msg if {
    not common.valid_performance_management
    msg := sprintf("HIGH: Resource '%s' must have a valid performance management record", [input.resource_id])
}

# --- Rule: Resources must have a valid availability management record ---
deny contains msg if {
    not common.valid_availability_management
    msg := sprintf("HIGH: Resource '%s' must have a valid availability management record", [input.resource_id])
}

# --- Rule: Resources must have a valid service level agreement ---
deny contains msg if {
    not common.valid_service_level_agreement
    msg := sprintf("HIGH: Resource '%s' must have a valid service level agreement", [input.resource_id])
}

# --- Rule: Resources must have a valid operational level agreement ---
deny contains msg if {
    not common.valid_operational_level_agreement
    msg := sprintf("HIGH: Resource '%s' must have a valid operational level agreement", [input.resource_id])
}

# --- Rule: Resources must have a valid underpinning contract ---
deny contains msg if {
    not common.valid_underpinning_contract
    msg := sprintf("HIGH: Resource '%s' must have a valid underpinning contract", [input.resource_id])
}

# --- Rule: Resources must have a valid service catalog entry ---
deny contains msg if {
    not common.valid_service_catalog
    msg := sprintf("HIGH: Resource '%s' must have a valid service catalog entry", [input.resource_id])
}

# --- Rule: Resources must have a valid service portfolio entry ---
deny contains msg if {
    not common.valid_service_portfolio
    msg := sprintf("HIGH: Resource '%s' must have a valid service portfolio entry", [input.resource_id])
}

# --- Rule: Resources must have a valid service design package ---
deny contains msg if {
    not common.valid_service_design_package
    msg := sprintf("HIGH: Resource '%s' must have a valid service design package", [input.resource_id])
}

# --- Rule: Resources must have a valid service transition plan ---
deny contains msg if {
    not common.valid_service_transition_plan
    msg := sprintf("HIGH: Resource '%s' must have a valid service transition plan", [input.resource_id])
}

# --- Rule: Resources must have a valid service operation plan ---
deny contains msg if {
    not common.valid_service_operation_plan
    msg := sprintf("HIGH: Resource '%s' must have a valid service operation plan", [input.resource_id])
}

# --- Rule: Resources must have a valid continual service improvement plan ---
deny contains msg if {
    not common.valid_continual_service_improvement_plan
    msg := sprintf("HIGH: Resource '%s' must have a valid continual service improvement plan", [input.resource_id])
}

# --- Rule: Resources must have a valid service reporting record ---
deny contains msg if {
    not common.valid_service_reporting
    msg := sprintf("HIGH: Resource '%s' must have a valid service reporting record", [input.resource_id])
}

# --- Rule: Resources must have a valid service measurement record ---
deny contains msg if {
    not common.valid_service_measurement
    msg := sprintf("HIGH: Resource '%s' must have a valid service measurement record", [input.resource_id])
}

# --- Rule: Resources must have a valid service level management record ---
deny contains msg if {
    not common.valid_service_level_management
    msg := sprintf("HIGH: Resource '%s' must have a valid service level management record", [input.resource_id])
}

# --- Rule: Resources must have a valid service continuity management record ---
deny contains msg if {
    not common.valid_service_continuity_management
    msg := sprintf("HIGH: Resource '%s' must have a valid service continuity management record", [input.resource_id])
}

# --- Rule: Resources must have a valid IT service continuity management record ---
deny contains msg if {
    not common.valid_it_service_continuity_management
    msg := sprintf("HIGH: Resource '%s' must have a valid IT service continuity management record", [input.resource_id])
}

# --- Rule: Resources must have a valid information security management record ---
deny contains msg if {
    not common.valid_information_security_management
    msg := sprintf("HIGH: Resource '%s' must have a valid information security management record", [input.resource_id])
}

# --- Rule: Resources must have a valid supplier management record ---
deny contains msg if {
    not common.valid_supplier_management
    msg := sprintf("HIGH: Resource '%s' must have a valid supplier management record", [input.resource_id])
}

# --- Rule: Resources must have a valid relationship management record ---
deny contains msg if {
    not common.valid_relationship_management
    msg := sprintf("HIGH: Resource '%s' must have a valid relationship management record", [input.resource_id])
}

# --- Rule: Resources must have a valid design coordination record ---
deny contains msg if {
    not common.valid_design_coordination
    msg := sprintf("HIGH: Resource '%s' must have a valid design coordination record", [input.resource_id])
}

# --- Rule: Resources must have a valid service asset and configuration management record ---
deny contains msg if {
    not common.valid_service_asset_and_configuration_management
    msg := sprintf("HIGH: Resource '%s' must have a valid service asset and configuration management record", [input.resource_id])
}

# --- Rule: Resources must have a valid release and deployment management record ---
deny contains msg if {
    not common.valid_release_and_deployment_management
    msg := sprintf("HIGH: Resource '%s' must have a valid release and deployment management record", [input.resource_id])
}

# --- Rule: Resources must have a valid service validation and testing record ---
deny contains msg if {
    not common.valid_service_validation_and_testing
    msg := sprintf("HIGH: Resource '%s' must have a valid service validation and testing record", [input.resource_id])
}

# --- Rule: Resources must have a valid knowledge management record ---
deny contains msg if {
    not common.valid_knowledge_management
    msg := sprintf("HIGH: Resource '%s' must have a valid knowledge management record", [input.resource_id])
}

# --- Rule: Resources must have a valid incident management record ---
deny contains msg if {
    not common.valid_incident_management
    msg := sprintf("HIGH: Resource '%s' must have a valid incident management record", [input.resource_id])
}

# --- Rule: Resources must have a valid problem management record ---
deny contains msg if {
    not common.valid_problem_management
    msg := sprintf("HIGH: Resource '%s' must have a valid problem management record", [input.resource_id])
}

# --- Rule: Resources must have a valid event management record ---
deny contains msg if {
    not common.valid_event_management
    msg := sprintf("HIGH: Resource '%s' must have a valid event management record", [input.resource_id])
}

# --- Rule: Resources must have a valid request fulfillment record ---
deny contains msg if {
    not common.valid_request_fulfillment
    msg := sprintf("HIGH: Resource '%s' must have a valid request fulfillment record", [input.resource_id])
}

# --- Rule: Resources must have a valid access management record ---
deny contains msg if {
    not common.valid_access_management
    msg := sprintf("HIGH: Resource '%s' must have a valid access management record", [input.resource_id])
}

# --- Rule: Resources must have a valid service desk record ---
deny contains msg if {
    not common.valid_service_desk
    msg := sprintf("HIGH: Resource '%s' must have a valid service desk record", [input.resource_id])
}

# --- Rule: Resources must have a valid technical management record ---
deny contains msg if {
    not common.valid_technical_management
    msg := sprintf("HIGH: Resource '%s' must have a valid technical management record", [input.resource_id])
}

# --- Rule: Resources must have a valid application management record ---
deny contains msg if {
    not common.valid_application_management
    msg := sprintf("HIGH: Resource '%s' must have a valid application management record", [input.resource_id])
}

# --- Rule: Resources must have a valid IT operations management record ---
deny contains msg if {
    not common.valid_it_operations_management
    msg := sprintf("HIGH: Resource '%s' must have a valid IT operations management record", [input.resource_id])
}

# --- Rule: Resources must have a valid facilities management record ---
deny contains msg if {
    not common.valid_facilities_management
    msg := sprintf("HIGH: Resource '%s' must have a valid facilities management record", [input.resource_id])
}

# --- Rule: Resources must have a valid infrastructure management record ---
deny contains msg if {
    not common.valid_infrastructure_management
    msg := sprintf("HIGH: Resource '%s' must have a valid infrastructure management record", [input.resource_id])
}

# --- Rule: Resources must have a valid network management record ---
deny contains msg if {
    not common.valid_network_management
    msg := sprintf("HIGH: Resource '%s' must have a valid network management record", [input.resource_id])
}

# --- Rule: Resources must have a valid storage management record ---
deny contains msg if {
    not common.valid_storage_management
    msg := sprintf("HIGH: Resource '%s' must have a valid storage management record", [input.resource_id])
}

# --- Rule: Resources must have a valid database management record ---
deny contains msg if {
    not common.valid_database_management
    msg := sprintf("HIGH: Resource '%s' must have a valid database management record", [input.resource_id])
}

# --- Rule: Resources must have a valid middleware management record ---
deny contains msg if {
    not common.valid_middleware_management
    msg := sprintf("HIGH: Resource '%s' must have a valid middleware management record", [input.resource_id])
}

# --- Rule: Resources must have a valid web management record ---
deny contains msg if {
    not common.valid_web_management
    msg := sprintf("HIGH: Resource '%s' must have a valid web management record", [input.resource_id])
}

# --- Rule: Resources must have a valid identity management record ---
deny contains msg if {
    not common.valid_identity_management
    msg := sprintf("HIGH: Resource '%s' must have a valid identity management record", [input.resource_id])
}

# --- Rule: Resources must have a valid entitlement management record ---
deny contains msg if {
    not common.valid_entitlement_management
    msg := sprintf("HIGH: Resource '%s' must have a valid entitlement management record", [input.resource_id])
}

# --- Rule: Resources must have a valid role management record ---
deny contains msg if {
    not common.valid_role_management
    msg := sprintf("HIGH: Resource '%s' must have a valid role management record", [input.resource_id])
}

# --- Rule: Resources must have a valid privilege management record ---
deny contains msg if {
    not common.valid_privilege_management
    msg := sprintf("HIGH: Resource '%s' must have a valid privilege management record", [input.resource_id])
}

# --- Rule: Resources must have a valid policy management record ---
deny contains msg if {
    not common.valid_policy_management
    msg := sprintf("HIGH: Resource '%s' must have a valid policy management record", [input.resource_id])
}

# --- Rule: Resources must have a valid compliance management record ---
deny contains msg if {
    not common.valid_compliance_management
    msg := sprintf("HIGH: Resource '%s' must have a valid compliance management record", [input.resource_id])
}

# --- Rule: Resources must have a valid risk management record ---
deny contains msg if {
    not common.valid_risk_management
    msg := sprintf("HIGH: Resource '%s' must have a valid risk management record", [input.resource_id])
}

# --- Rule: Resources must have a valid audit management record ---
deny contains msg if {
    not common.valid_audit_management
    msg := sprintf("HIGH: Resource '%s' must have a valid audit management record", [input.resource_id])
}

# --- Rule: Resources must have a valid governance record ---
deny contains msg if {
    not common.valid_governance
    msg := sprintf("HIGH: Resource '%s' must have a valid governance record", [input.resource_id])
}
