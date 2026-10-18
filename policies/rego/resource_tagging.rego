# resource_tagging.rego — Resource tagging governance for Data Center Commander
package datacenter.resource_tagging

import data.common

# --- Rule: All resources must have an owner tag ---
deny contains msg if {
    not common.has_owner
    msg := sprintf("HIGH: Resource '%s' must have an 'owner' tag", [input.resource_id])
}

# --- Rule: All resources must have a cost center tag ---
deny contains msg if {
    not common.has_cost_center
    msg := sprintf("HIGH: Resource '%s' must have a 'cost_center' tag", [input.resource_id])
}

# --- Rule: All resources must have a data classification tag ---
deny contains msg if {
    not common.has_data_classification
    msg := sprintf("HIGH: Resource '%s' must have a 'data_classification' tag", [input.resource_id])
}

# --- Rule: All resources must have a compliance scope tag ---
deny contains msg if {
    not common.has_compliance_scope
    msg := sprintf("HIGH: Resource '%s' must have a 'compliance_scope' tag", [input.resource_id])
}

# --- Rule: All resources must have an environment tag ---
deny contains msg if {
    not common.has_tag("environment")
    msg := sprintf("HIGH: Resource '%s' must have an 'environment' tag", [input.resource_id])
}

# --- Rule: All resources must have a project tag ---
deny contains msg if {
    not common.has_tag("project")
    msg := sprintf("MEDIUM: Resource '%s' must have a 'project' tag", [input.resource_id])
}

# --- Rule: All resources must have a team tag ---
deny contains msg if {
    not common.has_tag("team")
    msg := sprintf("MEDIUM: Resource '%s' must have a 'team' tag", [input.resource_id])
}

# --- Rule: All resources must have a service tag ---
deny contains msg if {
    not common.has_tag("service")
    msg := sprintf("MEDIUM: Resource '%s' must have a 'service' tag", [input.resource_id])
}

# --- Rule: All resources should have a version tag ---
deny contains msg if {
    not common.has_tag("version")
    msg := sprintf("LOW: Resource '%s' should have a 'version' tag", [input.resource_id])
}

# --- Rule: All resources should have a created date tag ---
deny contains msg if {
    not common.has_tag("created_date")
    msg := sprintf("LOW: Resource '%s' should have a 'created_date' tag", [input.resource_id])
}

# --- Rule: All resources should have a last reviewed date tag ---
deny contains msg if {
    not common.has_tag("last_reviewed")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'last_reviewed' tag", [input.resource_id])
}

# --- Rule: All resources should have a backup policy tag ---
deny contains msg if {
    not common.has_tag("backup_policy")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'backup_policy' tag", [input.resource_id])
}

# --- Rule: All resources should have a retention policy tag ---
deny contains msg if {
    not common.has_tag("retention_policy")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'retention_policy' tag", [input.resource_id])
}

# --- Rule: All resources should have a disaster recovery tag ---
deny contains msg if {
    not common.has_tag("disaster_recovery")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'disaster_recovery' tag", [input.resource_id])
}

# --- Rule: All resources should have a business continuity tag ---
deny contains msg if {
    not common.has_tag("business_continuity")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'business_continuity' tag", [input.resource_id])
}

# --- Rule: All resources should have a security assessment tag ---
deny contains msg if {
    not common.has_tag("security_assessment")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'security_assessment' tag", [input.resource_id])
}

# --- Rule: All resources should have a risk assessment tag ---
deny contains msg if {
    not common.has_tag("risk_assessment")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'risk_assessment' tag", [input.resource_id])
}

# --- Rule: All resources should have a compliance assessment tag ---
deny contains msg if {
    not common.has_tag("compliance_assessment")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'compliance_assessment' tag", [input.resource_id])
}

# --- Rule: All resources should have a audit trail tag ---
deny contains msg if {
    not common.has_tag("audit_trail")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'audit_trail' tag", [input.resource_id])
}

# --- Rule: All resources should have a configuration management tag ---
deny contains msg if {
    not common.has_tag("configuration_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'configuration_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a asset inventory tag ---
deny contains msg if {
    not common.has_tag("asset_inventory")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'asset_inventory' tag", [input.resource_id])
}

# --- Rule: All resources should have a vulnerability management tag ---
deny contains msg if {
    not common.has_tag("vulnerability_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'vulnerability_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a patch management tag ---
deny contains msg if {
    not common.has_tag("patch_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'patch_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a capacity management tag ---
deny contains msg if {
    not common.has_tag("capacity_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'capacity_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a performance management tag ---
deny contains msg if {
    not common.has_tag("performance_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'performance_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a availability management tag ---
deny contains msg if {
    not common.has_tag("availability_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'availability_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a service level agreement tag ---
deny contains msg if {
    not common.has_tag("service_level_agreement")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'service_level_agreement' tag", [input.resource_id])
}

# --- Rule: All resources should have a operational level agreement tag ---
deny contains msg if {
    not common.has_tag("operational_level_agreement")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'operational_level_agreement' tag", [input.resource_id])
}

# --- Rule: All resources should have a underpinning contract tag ---
deny contains msg if {
    not common.has_tag("underpinning_contract")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'underpinning_contract' tag", [input.resource_id])
}

# --- Rule: All resources should have a service catalog tag ---
deny contains msg if {
    not common.has_tag("service_catalog")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'service_catalog' tag", [input.resource_id])
}

# --- Rule: All resources should have a service portfolio tag ---
deny contains msg if {
    not common.has_tag("service_portfolio")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'service_portfolio' tag", [input.resource_id])
}

# --- Rule: All resources should have a service design package tag ---
deny contains msg if {
    not common.has_tag("service_design_package")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'service_design_package' tag", [input.resource_id])
}

# --- Rule: All resources should have a service transition plan tag ---
deny contains msg if {
    not common.has_tag("service_transition_plan")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'service_transition_plan' tag", [input.resource_id])
}

# --- Rule: All resources should have a service operation plan tag ---
deny contains msg if {
    not common.has_tag("service_operation_plan")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'service_operation_plan' tag", [input.resource_id])
}

# --- Rule: All resources should have a continual service improvement plan tag ---
deny contains msg if {
    not common.has_tag("continual_service_improvement_plan")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'continual_service_improvement_plan' tag", [input.resource_id])
}

# --- Rule: All resources should have a service reporting tag ---
deny contains msg if {
    not common.has_tag("service_reporting")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'service_reporting' tag", [input.resource_id])
}

# --- Rule: All resources should have a service measurement tag ---
deny contains msg if {
    not common.has_tag("service_measurement")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'service_measurement' tag", [input.resource_id])
}

# --- Rule: All resources should have a service level management tag ---
deny contains msg if {
    not common.has_tag("service_level_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'service_level_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a service continuity management tag ---
deny contains msg if {
    not common.has_tag("service_continuity_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'service_continuity_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a IT service continuity management tag ---
deny contains msg if {
    not common.has_tag("it_service_continuity_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'it_service_continuity_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a information security management tag ---
deny contains msg if {
    not common.has_tag("information_security_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'information_security_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a supplier management tag ---
deny contains msg if {
    not common.has_tag("supplier_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'supplier_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a relationship management tag ---
deny contains msg if {
    not common.has_tag("relationship_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'relationship_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a design coordination tag ---
deny contains msg if {
    not common.has_tag("design_coordination")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'design_coordination' tag", [input.resource_id])
}

# --- Rule: All resources should have a service asset and configuration management tag ---
deny contains msg if {
    not common.has_tag("service_asset_and_configuration_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'service_asset_and_configuration_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a release and deployment management tag ---
deny contains msg if {
    not common.has_tag("release_and_deployment_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'release_and_deployment_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a service validation and testing tag ---
deny contains msg if {
    not common.has_tag("service_validation_and_testing")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'service_validation_and_testing' tag", [input.resource_id])
}

# --- Rule: All resources should have a change management tag ---
deny contains msg if {
    not common.has_tag("change_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'change_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a knowledge management tag ---
deny contains msg if {
    not common.has_tag("knowledge_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'knowledge_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a incident management tag ---
deny contains msg if {
    not common.has_tag("incident_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'incident_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a problem management tag ---
deny contains msg if {
    not common.has_tag("problem_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'problem_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a event management tag ---
deny contains msg if {
    not common.has_tag("event_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'event_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a request fulfillment tag ---
deny contains msg if {
    not common.has_tag("request_fulfillment")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'request_fulfillment' tag", [input.resource_id])
}

# --- Rule: All resources should have a access management tag ---
deny contains msg if {
    not common.has_tag("access_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'access_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a service desk tag ---
deny contains msg if {
    not common.has_tag("service_desk")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'service_desk' tag", [input.resource_id])
}

# --- Rule: All resources should have a technical management tag ---
deny contains msg if {
    not common.has_tag("technical_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'technical_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a application management tag ---
deny contains msg if {
    not common.has_tag("application_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'application_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a IT operations management tag ---
deny contains msg if {
    not common.has_tag("it_operations_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'it_operations_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a facilities management tag ---
deny contains msg if {
    not common.has_tag("facilities_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'facilities_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a infrastructure management tag ---
deny contains msg if {
    not common.has_tag("infrastructure_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'infrastructure_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a network management tag ---
deny contains msg if {
    not common.has_tag("network_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'network_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a storage management tag ---
deny contains msg if {
    not common.has_tag("storage_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'storage_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a database management tag ---
deny contains msg if {
    not common.has_tag("database_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'database_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a middleware management tag ---
deny contains msg if {
    not common.has_tag("middleware_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'middleware_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a web management tag ---
deny contains msg if {
    not common.has_tag("web_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'web_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a identity management tag ---
deny contains msg if {
    not common.has_tag("identity_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'identity_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a entitlement management tag ---
deny contains msg if {
    not common.has_tag("entitlement_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'entitlement_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a role management tag ---
deny contains msg if {
    not common.has_tag("role_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'role_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a privilege management tag ---
deny contains msg if {
    not common.has_tag("privilege_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'privilege_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a policy management tag ---
deny contains msg if {
    not common.has_tag("policy_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'policy_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a compliance management tag ---
deny contains msg if {
    not common.has_tag("compliance_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'compliance_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a risk management tag ---
deny contains msg if {
    not common.has_tag("risk_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'risk_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a audit management tag ---
deny contains msg if {
    not common.has_tag("audit_management")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'audit_management' tag", [input.resource_id])
}

# --- Rule: All resources should have a governance tag ---
deny contains msg if {
    not common.has_tag("governance")
    msg := sprintf("MEDIUM: Resource '%s' should have a 'governance' tag", [input.resource_id])
}
