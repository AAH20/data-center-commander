"""Policy-as-code engine for Data Center Commander.

This package provides a comprehensive policy-as-code engine that supports:

- **OPA/Rego integration** — Parse and evaluate Rego policy documents
- **Sentinel integration** — Parse and evaluate HashiCorp Sentinel policies
- **Policy evaluation** — Evaluate policies against input documents
- **Policy bundles** — Group related policies for collective evaluation
- **Declarative policies** — Load policies from JSON/YAML files
- **Authz bridge** — Integrate with the existing authorization system

Architecture
------------

- :class:`PolicyEngine` — Main evaluation engine
- :class:`PolicyBundle` — Collection of related policies
- :class:`Policy` — Named collection of rules
- :class:`Rule` — Single policy rule with condition and effect
- :class:`PolicyDecision` — Outcome of policy evaluation
- :class:`RegoParser` — Parse Rego policy documents
- :class:`SentinelParser` — Parse Sentinel policy documents
- :class:`PolicyValidator` — Validate policy syntax and semantics
- :class:`PolicyDocument` — Load policies from JSON/YAML
- :class:`PolicyAuthzBridge` — Bridge to existing authz system

Usage
-----

.. code-block:: python

    from dcc.policy import PolicyEngine, Policy, Rule, Effect, PolicyBundle

    engine = PolicyEngine()

    policy = Policy(
        name="require-mfa-for-critical",
        description="Require MFA for critical resource access",
        rules=[
            Rule(
                name="deny-critical-without-mfa",
                effect=Effect.DENY,
                condition="input.resource.criticality == 'critical' and not input.environment.mfa_verified",
            ),
        ],
    )

    bundle = PolicyBundle(name="security", policies=[policy])
    engine.add_bundle(bundle)

    decision = engine.evaluate({
        "resource": {"criticality": "critical"},
        "environment": {"mfa_verified": False},
    })
    assert decision.denied
"""
from .errors import (
    PolicyError,
    PolicyEvaluationError,
    PolicyNotFoundError,
    PolicySyntaxError,
    PolicyValidationError,
    PolicyConflictError,
)
from .types import (
    DecisionEffect,
    Effect,
    Policy,
    PolicyDecision,
    PolicyBundle,
    Rule,
    RuleCondition,
)
from .engine import PolicyEngine
from .rego import RegoParser
from .sentinel import SentinelParser
from .validator import PolicyValidator
from .bundle import (
    create_default_policy_bundle,
    load_bundle_from_directory,
    load_bundle_from_file,
)
from .document import PolicyDocument
from .bridge import PolicyAuthzBridge

__all__ = [
    # Errors
    "PolicyError",
    "PolicyEvaluationError",
    "PolicyNotFoundError",
    "PolicySyntaxError",
    "PolicyValidationError",
    "PolicyConflictError",
    # Types
    "DecisionEffect",
    "Effect",
    "Policy",
    "PolicyDecision",
    "PolicyBundle",
    "Rule",
    "RuleCondition",
    # Engine
    "PolicyEngine",
    # Parsers
    "RegoParser",
    "SentinelParser",
    # Validation
    "PolicyValidator",
    # Bundle management
    "create_default_policy_bundle",
    "load_bundle_from_directory",
    "load_bundle_from_file",
    # Document loading
    "PolicyDocument",
    # Bridge
    "PolicyAuthzBridge",
]
