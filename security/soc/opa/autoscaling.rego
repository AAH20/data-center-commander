# OPA Rego Policy — Autoscaling Security Evaluation
# Data Center Commander SOC
# Version: 1.0.0
# Package: autoscaling
#
# This policy evaluates autoscaling configurations to ensure they meet
# security and availability requirements.

package autoscaling

import future.keywords.if
import future.keywords.in

# =============================================================================
# DEFAULT DECISION
# =============================================================================

default allow := false

# =============================================================================
# POLICY PARAMETERS
# =============================================================================

# Minimum replicas for high availability
min_replicas := 2

# Maximum replicas to prevent resource exhaustion
max_replicas := 10

# Target CPU utilization percentage
target_cpu_utilization := 70

# Target memory utilization percentage
target_memory_utilization := 80

# =============================================================================
# MAIN POLICY RULES
# =============================================================================

# Allow if all checks pass
allow if {
    not has_insufficient_replicas
    not has_excessive_replicas
    not has_missing_hpa
    not has_missing_vpa
    not has_missing_pdb
    not has_invalid_cpu_target
    not has_invalid_memory_target
    not has_missing_metrics
    not has_missing_scaling_policies
    not has_missing_resource_requests
    not has_missing_resource_limits
    not has_missing_priority_class
    not has_missing_affinity_rules
    not has_missing_topology_spread
    not has_missing_runtime_class
    not has_missing_graceful_shutdown
    not has_missing_prestop_hook
    not has_missing_termination_grace_period
}

# =============================================================================
# REPLICA CHECKS
# =============================================================================

has_insufficient_replicas if {
    input.min_replicas < min_replicas
}

has_excessive_replicas if {
    input.max_replicas > max_replicas
}

# =============================================================================
# HPA/VPA CHECKS
# =============================================================================

has_missing_hpa if {
    not input.hpa_configured
}

has_missing_vpa if {
    not input.vpa_configured
}

# =============================================================================
# PDB CHECKS
# =============================================================================

has_missing_pdb if {
    not input.pdb_configured
}

# =============================================================================
# TARGET UTILIZATION CHECKS
# =============================================================================

has_invalid_cpu_target if {
    input.target_cpu_utilization < 50
}

has_invalid_cpu_target if {
    input.target_cpu_utilization > 90
}

has_invalid_memory_target if {
    input.target_memory_utilization < 50
}

has_invalid_memory_target if {
    input.target_memory_utilization > 95
}

# =============================================================================
# METRICS CHECKS
# =============================================================================

has_missing_metrics if {
    not input.metrics_configured
}

# =============================================================================
# SCALING POLICY CHECKS
# =============================================================================

has_missing_scaling_policies if {
    not input.scale_up_policy
}

has_missing_scaling_policies if {
    not input.scale_down_policy
}

# =============================================================================
# RESOURCE CHECKS
# =============================================================================

has_missing_resource_requests if {
    not input.resource_requests
}

has_missing_resource_limits if {
    not input.resource_limits
}

# =============================================================================
# SCHEDULING CHECKS
# =============================================================================

has_missing_priority_class if {
    not input.priority_class
}

has_missing_affinity_rules if {
    not input.affinity_rules
}

has_missing_topology_spread if {
    not input.topology_spread_constraints
}

has_missing_runtime_class if {
    not input.runtime_class
}

# =============================================================================
# LIFECYCLE CHECKS
# =============================================================================

has_missing_graceful_shutdown if {
    not input.graceful_shutdown
}

has_missing_prestop_hook if {
    not input.prestop_hook
}

has_missing_termination_grace_period if {
    not input.termination_grace_period
}

# =============================================================================
# VIOLATION MESSAGES
# =============================================================================

violations contains msg if {
    has_insufficient_replicas
    msg := sprintf("HIGH: Minimum replicas (%d) is less than required (%d)", [input.min_replicas, min_replicas])
}

violations contains msg if {
    has_excessive_replicas
    msg := sprintf("MEDIUM: Maximum replicas (%d) exceeds limit (%d)", [input.max_replicas, max_replicas])
}

violations contains msg if {
    has_missing_hpa
    msg := "HIGH: Horizontal Pod Autoscaler is not configured"
}

violations contains msg if {
    has_missing_vpa
    msg := "MEDIUM: Vertical Pod Autoscaler is not configured"
}

violations contains msg if {
    has_missing_pdb
    msg := "HIGH: Pod Disruption Budget is not configured"
}

violations contains msg if {
    has_invalid_cpu_target
    msg := sprintf("MEDIUM: CPU target utilization (%d%%) is outside acceptable range (50-90%%)", [input.target_cpu_utilization])
}

violations contains msg if {
    has_invalid_memory_target
    msg := sprintf("MEDIUM: Memory target utilization (%d%%) is outside acceptable range (50-95%%)", [input.target_memory_utilization])
}

violations contains msg if {
    has_missing_metrics
    msg := "HIGH: Metrics are not configured for autoscaling"
}

violations contains msg if {
    has_missing_scaling_policies
    msg := "HIGH: Scaling policies are not configured"
}

violations contains msg if {
    has_missing_resource_requests
    msg := "MEDIUM: Resource requests are not configured"
}

violations contains msg if {
    has_missing_resource_limits
    msg := "MEDIUM: Resource limits are not configured"
}

violations contains msg if {
    has_missing_priority_class
    msg := "LOW: Priority class is not configured"
}

violations contains msg if {
    has_missing_affinity_rules
    msg := "LOW: Affinity rules are not configured"
}

violations contains msg if {
    has_missing_topology_spread
    msg := "LOW: Topology spread constraints are not configured"
}

violations contains msg if {
    has_missing_runtime_class
    msg := "LOW: Runtime class is not configured"
}

violations contains msg if {
    has_missing_graceful_shutdown
    msg := "MEDIUM: Graceful shutdown is not configured"
}

violations contains msg if {
    has_missing_prestop_hook
    msg := "MEDIUM: preStop hook is not configured"
}

violations contains msg if {
    has_missing_termination_grace_period
    msg := "MEDIUM: Termination grace period is not configured"
}

# =============================================================================
# METADATA
# =============================================================================

metadata := {
    "policy": "autoscaling",
    "version": "1.0.0",
    "description": "Autoscaling security policy for Data Center Commander",
    "author": "Security Team",
    "created": "2026-09-29"
}
