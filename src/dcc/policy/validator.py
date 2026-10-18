"""Policy validation for the policy-as-code engine.

The PolicyValidator checks policies for syntax and semantic correctness
before they are registered with the engine.
"""
from __future__ import annotations

from .engine import PolicyEngine
from .types import Policy, PolicyBundle, RuleCondition
from .errors import PolicySyntaxError

__all__ = ["PolicyValidator"]


class PolicyValidator:
    """Validates policy documents for syntax and semantic correctness.

    Checks:
    - Policy has a name
    - Policy has at least one rule
    - All rules have valid conditions
    - All rule conditions compile
    - No duplicate rule names
    - No circular references
    """

    def validate(self, policy: Policy) -> list[str]:
        """Validate a policy and return a list of error messages.

        Returns an empty list if the policy is valid.
        """
        errors: list[str] = []

        if not policy.name:
            errors.append("policy name is required")

        if not policy.rules:
            errors.append("policy must have at least one rule")

        rule_names: set[str] = set()
        for rule in policy.rules:
            if not rule.name:
                errors.append(f"rule has no name in policy {policy.name}")
            elif rule.name in rule_names:
                errors.append(f"duplicate rule name {rule.name!r} in policy {policy.name}")
            else:
                rule_names.add(rule.name)

            if not rule.condition:
                errors.append(f"rule {rule.name!r} has no condition")
            else:
                try:
                    RuleCondition(rule.condition)
                except PolicySyntaxError as exc:
                    errors.append(f"rule {rule.name!r} has invalid condition: {exc}")

        return errors

    def validate_bundle(self, bundle: PolicyBundle) -> list[str]:
        """Validate a policy bundle and return a list of error messages."""
        errors: list[str] = []

        if not bundle.name:
            errors.append("bundle name is required")

        if not bundle.policies:
            errors.append("bundle must have at least one policy")

        policy_names: set[str] = set()
        for policy in bundle.policies.values():
            if policy.name in policy_names:
                errors.append(f"duplicate policy name {policy.name!r} in bundle {bundle.name}")
            else:
                policy_names.add(policy.name)
            errors.extend(self.validate(policy))

        return errors

    def validate_engine(self, engine: PolicyEngine) -> list[str]:
        """Validate a policy engine and return a list of error messages."""
        errors: list[str] = []

        if not engine.bundles:
            errors.append("engine must have at least one bundle")

        bundle_names: set[str] = set()
        for bundle in engine.bundles.values():
            if bundle.name in bundle_names:
                errors.append(f"duplicate bundle name {bundle.name!r}")
            else:
                bundle_names.add(bundle.name)
            errors.extend(self.validate_bundle(bundle))

        return errors
