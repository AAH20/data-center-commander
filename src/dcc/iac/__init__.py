"""IaC, auto-scaling, and serverless runtime modules.

Surpasses Terraform, AWS Auto Scaling, and AWS Lambda with:
- Python-native declarative DSL with compile-time validation
- Real-time drift detection with automatic rollback
- Predictive auto-scaling based on historical patterns
- Warm pool for zero cold start latency
"""
from dcc.iac.autoscaler import AutoScaler, ScalingDecision, ScalingPolicy, ScalingTrigger
from dcc.iac.dsl import (
    InfrastructureDefinition,
    Resource,
    ResourceType,
    ValidationError,
    define_resource,
    define_tenant,
)
from dcc.iac.engine import (
    ApplyResult,
    DriftReport,
    EngineAction,
    PlanResult,
    PlanStep,
    apply_plan,
    detect_drift,
    generate_plan,
)
from dcc.iac.runtime import (
    FunctionDefinition,
    FunctionResult,
    RuntimeExecutor,
    WarmPool,
)

__all__ = [
    "AutoScaler",
    "ApplyResult",
    "DriftReport",
    "EngineAction",
    "FunctionDefinition",
    "FunctionResult",
    "InfrastructureDefinition",
    "PlanResult",
    "PlanStep",
    "Resource",
    "ResourceType",
    "RuntimeExecutor",
    "ScalingDecision",
    "ScalingPolicy",
    "ScalingTrigger",
    "ValidationError",
    "WarmPool",
    "apply_plan",
    "define_resource",
    "define_tenant",
    "detect_drift",
    "generate_plan",
]
