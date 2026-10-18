# OPA Rego Policy — SOC Integration and Alert Evaluation
# Data Center Commander SOC
# Version: 1.0.0
# Package: soc
#
# This policy evaluates security events and determines alert severity,
# escalation paths, and automated response actions.

package soc

import future.keywords.if
import future.keywords.in

# =============================================================================
# DEFAULT DECISION
# =============================================================================

default allow := true

# =============================================================================
# ALERT SEVERITY MAPPING
# =============================================================================

# Map vulnerability severity to alert severity
alert_severity := "critical" if {
    input.event_type == "vulnerability"
    input.severity == "CRITICAL"
}

alert_severity := "high" if {
    input.event_type == "vulnerability"
    input.severity == "HIGH"
}

alert_severity := "medium" if {
    input.event_type == "vulnerability"
    input.severity == "MEDIUM"
}

alert_severity := "low" if {
    input.event_type == "vulnerability"
    input.severity == "LOW"
}

# Map misconfiguration severity to alert severity
alert_severity := "high" if {
    input.event_type == "misconfiguration"
    input.severity == "CRITICAL"
}

alert_severity := "medium" if {
    input.event_type == "misconfiguration"
    input.severity == "HIGH"
}

alert_severity := "low" if {
    input.event_type == "misconfiguration"
    input.severity == "MEDIUM"
}

# Map secret severity to alert severity
alert_severity := "critical" if {
    input.event_type == "secret"
}

# Map policy violation severity to alert severity
alert_severity := "critical" if {
    input.event_type == "policy_violation"
    input.severity == "CRITICAL"
}

alert_severity := "high" if {
    input.event_type == "policy_violation"
    input.severity == "HIGH"
}

alert_severity := "medium" if {
    input.event_type == "policy_violation"
    input.severity == "MEDIUM"
}

# =============================================================================
# ALERT ROUTING
# =============================================================================

# Determine alert routing based on severity
alert_route := "pagerduty" if {
    alert_severity == "critical"
}

alert_route := "slack" if {
    alert_severity == "high"
}

alert_route := "slack" if {
    alert_severity == "medium"
}

alert_route := "email" if {
    alert_severity == "low"
}

# =============================================================================
# AUTO-REMEDIATION
# =============================================================================

# Determine if auto-remediation should be attempted
auto_remediate := true if {
    input.event_type == "vulnerability"
    input.severity == "CRITICAL"
    input.auto_remediation_enabled
}

auto_remediate := true if {
    input.event_type == "misconfiguration"
    input.severity == "CRITICAL"
    input.auto_remediation_enabled
}

auto_remediate := false

# =============================================================================
# AUTO-REMEDIATION ACTIONS
# =============================================================================

# Determine remediation action
remediation_action := "rollback" if {
    input.event_type == "vulnerability"
    input.severity == "CRITICAL"
    input.previous_version_available
}

remediation_action := "reschedule" if {
    input.event_type == "vulnerability"
    input.severity == "CRITICAL"
    not input.previous_version_available
}

remediation_action := "patch" if {
    input.event_type == "misconfiguration"
    input.severity == "CRITICAL"
    input.patch_available
}

remediation_action := "quarantine" if {
    input.event_type == "secret"
}

remediation_action := "none"

# =============================================================================
# ESCALATION
# =============================================================================

# Determine escalation level
escalation_level := 1 if {
    alert_severity == "critical"
}

escalation_level := 2 if {
    alert_severity == "high"
}

escalation_level := 3 if {
    alert_severity == "medium"
}

escalation_level := 4 if {
    alert_severity == "low"
}

# Determine if escalation is needed
requires_escalation if {
    alert_severity == "critical"
}

requires_escalation if {
    alert_severity == "high"
    input.repeat_count > 3
}

# =============================================================================
# NOTIFICATION CHANNELS
# =============================================================================

# Determine notification channels
notification_channels := ["pagerduty", "slack", "email"] if {
    alert_severity == "critical"
}

notification_channels := ["slack", "email"] if {
    alert_severity == "high"
}

notification_channels := ["slack"] if {
    alert_severity == "medium"
}

notification_channels := ["email"] if {
    alert_severity == "low"
}

# =============================================================================
# ALERT SUPPRESSION
# =============================================================================

# Check if alert should be suppressed
suppress_alert if {
    input.suppressed == true
}

suppress_alert if {
    input.maintenance_window == true
}

suppress_alert if {
    input.alert_count > 10
    input.time_window_minutes < 60
}

# =============================================================================
# COMPLIANCE MAPPING
# =============================================================================

# Map to compliance frameworks
compliance_frameworks contains "CIS" if {
    input.event_type == "vulnerability"
}

compliance_frameworks contains "NIST-800-53" if {
    input.event_type == "vulnerability"
}

compliance_frameworks contains "PCI-DSS" if {
    input.event_type == "secret"
}

compliance_frameworks contains "GDPR" if {
    input.event_type == "secret"
    input.contains_pii
}

compliance_frameworks contains "HIPAA" if {
    input.event_type == "secret"
    input.contains_phi
}

compliance_frameworks contains "SOC2" if {
    input.event_type == "policy_violation"
}

compliance_frameworks contains "ISO27001" if {
    input.event_type == "policy_violation"
}

# =============================================================================
# METADATA
# =============================================================================

metadata := {
    "policy": "soc",
    "version": "1.0.0",
    "description": "SOC integration policy for Data Center Commander",
    "author": "Security Team",
    "created": "2026-09-29"
}
