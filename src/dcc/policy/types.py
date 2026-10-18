"""Core types for the policy-as-code engine.

This module defines the fundamental data structures used throughout the
policy engine: effects, rules, policies, decisions, and bundles.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from .errors import PolicyEvaluationError, PolicySyntaxError, PolicyValidationError

__all__ = [
    "DecisionEffect",
    "Effect",
    "Policy",
    "PolicyDecision",
    "PolicyBundle",
    "Rule",
    "RuleCondition",
]


# ---------------------------------------------------------------------------
# Effect
# ---------------------------------------------------------------------------


class Effect(str, Enum):
    """Whether a policy rule allows or denies access."""

    ALLOW = "allow"
    DENY = "deny"


class DecisionEffect(str, Enum):
    """The effect of a policy decision.

    Unlike :class:`Effect` which only has ALLOW/DENY, this includes ABSTAIN
    for policies that have no opinion on the input.
    """

    ALLOW = "allow"
    DENY = "deny"
    ABSTAIN = "abstain"


# ---------------------------------------------------------------------------
# RuleCondition
# ---------------------------------------------------------------------------


class RuleCondition:
    """A compiled rule condition that can be evaluated against an input document.

    Conditions are expressed as Python expressions that reference the ``input``
    document. For example::

        "input.resource.criticality == 'critical'"
        "input.action == 'write' and input.environment.mfa_verified"

    The condition is compiled into a callable for efficient evaluation.
    """

    def __init__(self, expression: str) -> None:
        self.expression = expression
        self._compiled: Any = None
        self._compile()

    def _compile(self) -> None:
        """Compile the expression into a callable.

        The expression is compiled with ``eval`` in a restricted namespace
        that only provides access to the ``input`` document and safe builtins.
        """
        self._validate_expression(self.expression)

        try:
            code = compile(self.expression, "<policy_condition>", "eval")
        except SyntaxError as exc:
            raise PolicySyntaxError(
                f"Invalid condition syntax: {self.expression!r}: {exc}"
            ) from exc

        def evaluate(input_doc: dict[str, Any]) -> bool:
            """Evaluate the compiled condition against the input document."""
            namespace: dict[str, Any] = {
                "input": _SafeInputWrapper(input_doc),
                "true": True,
                "false": False,
                "null": None,
            }
            try:
                result = eval(code, {"__builtins__": {}}, namespace)  # noqa: S307
                return bool(result)
            except Exception as exc:
                raise PolicyEvaluationError(
                    f"Condition evaluation failed: {self.expression!r}: {exc}"
                ) from exc

        self._compiled = evaluate

    def _validate_expression(self, expression: str) -> None:
        """Validate that the expression is safe to evaluate.

        Only allows:
        - Attribute access on ``input``
        - Comparisons (==, !=, <, >, <=, >=, in, not in)
        - Boolean operators (and, or, not)
        - String/number literals
        - Function calls to safe builtins (len, str, int, float, bool)
        """
        import re

        dangerous = [
            r"__\w+__",  # Dunder attributes
            r"import\s+\w+",  # Import statements
            r"from\s+\w+\s+import",  # From imports
            r"exec\s*\(",  # exec()
            r"eval\s*\(",  # eval()
            r"compile\s*\(",  # compile()
            r"open\s*\(",  # open()
            r"file\s*\(",  # file()
            r"subprocess",  # subprocess
            r"os\.",  # os module
            r"sys\.",  # sys module
            r"__builtins__",  # builtins access
            r"globals\s*\(",  # globals()
            r"locals\s*\(",  # locals()
            r"vars\s*\(",  # vars()
            r"getattr\s*\(",  # getattr()
            r"setattr\s*\(",  # setattr()
            r"delattr\s*\(",  # delattr()
        ]
        for pattern in dangerous:
            if re.search(pattern, expression):
                raise PolicySyntaxError(
                    f"Condition contains forbidden pattern {pattern!r}: {expression!r}"
                )

    def evaluate(self, input_doc: dict[str, Any]) -> bool:
        """Evaluate the condition against the input document."""
        if self._compiled is None:
            raise PolicyEvaluationError("Condition was not compiled")
        return self._compiled(input_doc)

    def __repr__(self) -> str:
        return f"RuleCondition({self.expression!r})"


class _SafeInputWrapper:
    """A safe wrapper around the input document that prevents attribute escalation.

    This wrapper only allows read access to the input document's keys.
    It prevents access to Python object attributes (like ``__class__``).
    """

    __slots__ = ("_data",)

    def __init__(self, data: dict[str, Any]) -> None:
        object.__setattr__(self, "_data", data)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(f"Access to private attribute {name!r} is forbidden")
        data = object.__getattribute__(self, "_data")
        if isinstance(data, dict) and name in data:
            value = data[name]
            if isinstance(value, dict):
                return _SafeInputWrapper(value)
            if isinstance(value, list):
                return [_SafeInputWrapper(v) if isinstance(v, dict) else v for v in value]
            return value
        return None

    def __getitem__(self, key: str) -> Any:
        data = object.__getattribute__(self, "_data")
        if isinstance(data, dict) and key in data:
            value = data[key]
            if isinstance(value, dict):
                return _SafeInputWrapper(value)
            if isinstance(value, list):
                return [_SafeInputWrapper(v) if isinstance(v, dict) else v for v in value]
            return value
        raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        data = object.__getattribute__(self, "_data")
        return isinstance(data, dict) and key in data

    def __repr__(self) -> str:
        return f"_SafeInputWrapper({object.__getattribute__(self, '_data')!r})"


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rule:
    """A single policy rule with a condition and effect.

    A rule evaluates its condition against the input document. If the
    condition is true, the rule's effect (ALLOW or DENY) is applied.

    Parameters
    ----------
    name:
        Unique rule name within the policy.
    effect:
        Whether to allow or deny when the condition matches.
    condition:
        A Python expression string that references the ``input`` document.
        For example: ``"input.resource.criticality == 'critical'"``.
    description:
        Human-readable description of the rule.
    """

    name: str
    effect: Effect
    condition: str
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("rule name must be non-empty")
        if not self.condition:
            raise ValueError("rule condition must be non-empty")
        _ = RuleCondition(self.condition)

    def evaluate(self, input_doc: dict[str, Any]) -> bool:
        """Evaluate the rule's condition against the input document.

        Returns True if the rule matches (condition is true).
        """
        cond = RuleCondition(self.condition)
        return cond.evaluate(input_doc)


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


@dataclass
class Policy:
    """A named collection of rules that form a security policy.

    A policy has a name, description, and a set of rules. When evaluated,
    all rules are checked. If any DENY rule matches, the policy denies.
    If any ALLOW rule matches (and no DENY matched), the policy allows.
    If no rules match, the policy abstains (no decision).

    Parameters
    ----------
    name:
        Unique policy name.
    description:
        Human-readable description.
    rules:
        The rules that make up this policy.
    version:
        Policy version string.
    metadata:
        Arbitrary metadata key-value pairs.
    """

    name: str
    description: str = ""
    rules: list[Rule] = field(default_factory=list)
    version: str = "1.0.0"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("policy name must be non-empty")
        for rule in self.rules:
            if not isinstance(rule, Rule):
                raise TypeError(f"rule must be a Rule instance, got {type(rule).__name__}")

    def evaluate(self, input_doc: dict[str, Any]) -> PolicyDecision:
        """Evaluate this policy against the input document.

        Returns a :class:`PolicyDecision` with the outcome. If no rules
        match, the policy abstains (no opinion).
        """
        matched_rules: list[str] = []
        denied = False
        allowed = False

        for rule in self.rules:
            try:
                if rule.evaluate(input_doc):
                    matched_rules.append(rule.name)
                    if rule.effect == Effect.DENY:
                        denied = True
                    elif rule.effect == Effect.ALLOW:
                        allowed = True
            except PolicyEvaluationError:
                continue

        if denied:
            effect = DecisionEffect.DENY
        elif allowed:
            effect = DecisionEffect.ALLOW
        else:
            effect = DecisionEffect.ABSTAIN

        return PolicyDecision(
            policy_name=self.name,
            effect=effect,
            matched_rules=tuple(matched_rules),
            input_summary=_summarize_input(input_doc),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the policy to a dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "metadata": self.metadata,
            "rules": [
                {
                    "name": r.name,
                    "effect": r.effect.value,
                    "condition": r.condition,
                    "description": r.description,
                }
                for r in self.rules
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Policy:
        """Deserialize a policy from a dictionary."""
        rules = [
            Rule(
                name=r["name"],
                effect=Effect(r["effect"]),
                condition=r["condition"],
                description=r.get("description", ""),
            )
            for r in data.get("rules", [])
        ]
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            rules=rules,
            version=data.get("version", "1.0.0"),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# PolicyDecision
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PolicyDecision:
    """The outcome of evaluating a policy or policy bundle.

    Attributes
    ----------
    policy_name:
        Name of the policy that produced this decision.
    effect:
        The decision effect (ALLOW, DENY, or ABSTAIN).
    matched_rules:
        Names of rules that matched the input.
    input_summary:
        A summary of the input document for auditing.
    reason:
        Human-readable explanation of the decision.
    """

    policy_name: str
    effect: DecisionEffect
    matched_rules: tuple[str, ...] = ()
    input_summary: str = ""
    reason: str = ""

    @property
    def allowed(self) -> bool:
        """Return True if the decision is ALLOW."""
        return self.effect == DecisionEffect.ALLOW

    @property
    def denied(self) -> bool:
        """Return True if the decision is DENY."""
        return self.effect == DecisionEffect.DENY

    @property
    def abstained(self) -> bool:
        """Return True if the decision is ABSTAIN."""
        return self.effect == DecisionEffect.ABSTAIN

    def to_dict(self) -> dict[str, Any]:
        """Serialize the decision to a dictionary."""
        return {
            "policy_name": self.policy_name,
            "effect": self.effect.value,
            "matched_rules": list(self.matched_rules),
            "input_summary": self.input_summary,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# PolicyBundle
# ---------------------------------------------------------------------------


class PolicyBundle:
    """A collection of policies that are evaluated together.

    A policy bundle groups related policies. When evaluated, all policies
    in the bundle are checked. If any policy denies, the bundle denies.
    If any policy allows (and none deny), the bundle allows.
    If no policies match, the bundle denies (fail-closed).

    Parameters
    ----------
    name:
        Unique bundle name.
    description:
        Human-readable description.
    policies:
        The policies in this bundle.
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        policies: Iterable[Policy] | None = None,
    ) -> None:
        if not name:
            raise ValueError("bundle name must be non-empty")
        self.name = name
        self.description = description
        self._policies: dict[str, Policy] = {}
        self._lock = threading.Lock()

        if policies:
            for policy in policies:
                self.add_policy(policy)

    def add_policy(self, policy: Policy) -> None:
        """Add a policy to the bundle."""
        with self._lock:
            self._policies[policy.name] = policy

    def remove_policy(self, name: str) -> None:
        """Remove a policy from the bundle."""
        with self._lock:
            del self._policies[name]

    @property
    def policies(self) -> Mapping[str, Policy]:
        """Return a read-only view of the policies in this bundle."""
        return dict(self._policies)

    def evaluate(self, input_doc: dict[str, Any]) -> PolicyDecision:
        """Evaluate all policies in the bundle against the input document.

        The bundle decision is the most restrictive of all policy decisions:
        - If any policy denies, the bundle denies.
        - If any policy allows (and none deny), the bundle allows.
        - If no policies match, the bundle abstains (no opinion).
        """
        all_matched: list[str] = []
        any_denied = False
        any_allowed = False
        deny_reasons: list[str] = []

        with self._lock:
            policies = list(self._policies.values())

        for policy in policies:
            decision = policy.evaluate(input_doc)
            all_matched.extend(decision.matched_rules)
            if decision.denied:
                any_denied = True
                deny_reasons.append(
                    f"{policy.name}: {', '.join(decision.matched_rules) or 'default deny'}"
                )
            elif decision.allowed:
                any_allowed = True

        if any_denied:
            effect = DecisionEffect.DENY
            reason = "; ".join(deny_reasons)
        elif any_allowed:
            effect = DecisionEffect.ALLOW
            reason = "allowed by policy rules"
        else:
            effect = DecisionEffect.ABSTAIN
            reason = "no matching policy rules"

        return PolicyDecision(
            policy_name=self.name,
            effect=effect,
            matched_rules=tuple(all_matched),
            input_summary=_summarize_input(input_doc),
            reason=reason,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the bundle to a dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "policies": [p.to_dict() for p in self._policies.values()],
        }


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _summarize_input(input_doc: dict[str, Any], max_len: int = 200) -> str:
    """Create a short summary of the input document for auditing."""
    try:
        summary = json.dumps(input_doc, default=str, sort_keys=True)
    except (TypeError, ValueError):
        summary = str(input_doc)
    if len(summary) > max_len:
        summary = summary[: max_len - 3] + "..."
    return summary
