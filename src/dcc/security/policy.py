"""Policy-as-code engine: OPA/Rego integration for security policies.

This module provides a policy-as-code engine that implements an OPA/Rego-compatible
policy evaluation model. It allows security policies to be defined as code (in a
Rego-like DSL) and evaluated against input documents at runtime.

Architecture
------------

- :class:`Policy` — A named collection of rules (allow/deny) with metadata.
- :class:`Rule` — A single policy rule with a condition and effect.
- :class:`PolicyEngine` — Evaluates policies against input documents.
- :class:`PolicyBundle` — A collection of related policies that are evaluated together.
- :class:`PolicyDecision` — The outcome of a policy evaluation.
- :class:`RegoParser` — Parses Rego-like policy documents into executable rules.
- :class:`PolicyValidator` — Validates policy syntax and semantics.

The engine supports the OPA/Rego evaluation model:

1. **Input** — A JSON-like document representing the request context.
2. **Policy** — A set of rules that evaluate the input.
3. **Decision** — The final allow/deny decision with supporting evidence.

Usage
-----

.. code-block:: python

    from dcc.security.policy import PolicyEngine, Policy, Rule, Effect

    engine = PolicyEngine()

    # Define a policy
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

    engine.add_policy(policy)

    # Evaluate
    decision = engine.evaluate(
        input_doc={
            "resource": {"criticality": "critical"},
            "environment": {"mfa_verified": False},
        }
    )
    assert decision.effect == Effect.DENY
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Iterable,
    Mapping,
    Optional,
    Sequence,
    Union,
)

from .authz import AuthorizationContext, Effect, Policy as AuthzPolicy
from .tenant import current_tenant, get_tenant_id

__all__ = [
    "DecisionEffect",
    "Effect",
    "PolicyDecision",
    "Policy",
    "PolicyEngine",
    "PolicyBundle",
    "PolicyValidationError",
    "RegoParser",
    "Rule",
    "RuleCondition",
    "PolicyValidator",
    "create_default_policy_bundle",
    "create_default_policy_engine",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PolicyValidationError(ValueError):
    """Raised when a policy document fails validation.

    Attributes
    ----------
    errors:
        A list of validation error messages.
    """

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        self.errors = errors or []
        super().__init__(message)


class PolicyEvaluationError(RuntimeError):
    """Raised when policy evaluation fails due to an internal error."""


class PolicySyntaxError(PolicyValidationError):
    """Raised when a policy document has a syntax error."""


# ---------------------------------------------------------------------------
# Core value types
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
        self._compiled: Callable[[dict[str, Any]], bool] | None = None
        self._compile()

    def _compile(self) -> None:
        """Compile the expression into a callable.

        The expression is compiled with ``eval`` in a restricted namespace
        that only provides access to the ``input`` document and safe builtins.
        """
        # Validate the expression for safety
        self._validate_expression(self.expression)

        # Compile the expression
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
        # Block dangerous patterns
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
        # Return None for missing keys so conditions like
        # "input.tenant_id is not None" work correctly
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
        # Validate the condition compiles
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
        # Validate all rules
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
                # If a rule fails to evaluate, skip it (fail-open for that rule)
                continue

        # DENY takes precedence over ALLOW
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


class DecisionEffect(str, Enum):
    """The effect of a policy decision.

    Unlike :class:`Effect` which only has ALLOW/DENY, this includes ABSTAIN
    for policies that have no opinion on the input.
    """

    ALLOW = "allow"
    DENY = "deny"
    ABSTAIN = "abstain"


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
# PolicyEngine
# ---------------------------------------------------------------------------


class PolicyEngine:
    """Main policy evaluation engine.

    The engine maintains a registry of policy bundles and evaluates them
    against input documents. It supports:

    - Adding/removing policy bundles
    - Evaluating input documents against all registered bundles
    - Tenant-scoped policy evaluation
    - Policy decision caching (optional)

    Parameters
    ----------
    bundles:
        Initial policy bundles to register.
    default_deny:
        If True (default), unmatched requests are denied.
    """

    def __init__(
        self,
        bundles: Iterable[PolicyBundle] | None = None,
        *,
        default_deny: bool = True,
    ) -> None:
        self._bundles: dict[str, PolicyBundle] = {}
        self._default_deny = default_deny
        self._lock = threading.Lock()

        if bundles:
            for bundle in bundles:
                self.add_bundle(bundle)

    def add_bundle(self, bundle: PolicyBundle) -> None:
        """Add a policy bundle to the engine."""
        with self._lock:
            self._bundles[bundle.name] = bundle

    def remove_bundle(self, name: str) -> None:
        """Remove a policy bundle from the engine."""
        with self._lock:
            del self._bundles[name]

    @property
    def bundles(self) -> Mapping[str, PolicyBundle]:
        """Return a read-only view of registered bundles."""
        return dict(self._bundles)

    def evaluate(
        self,
        input_doc: dict[str, Any],
        *,
        tenant_id: str | None = None,
    ) -> PolicyDecision:
        """Evaluate the input document against all registered policy bundles.

        Parameters
        ----------
        input_doc:
            The input document to evaluate. Should contain ``resource``,
            ``action``, ``subject``, and ``environment`` keys.
        tenant_id:
            Optional tenant ID for tenant-scoped evaluation. If provided,
            only bundles whose policies have a matching ``tenant_id``
            metadata key are evaluated.

        Returns
        -------
        PolicyDecision
            The final decision after evaluating all bundles.
        """
        # Auto-populate tenant from context if not provided
        if tenant_id is None:
            try:
                tenant_id = get_tenant_id()
            except Exception:
                pass

        all_matched: list[str] = []
        any_denied = False
        any_allowed = False
        deny_reasons: list[str] = []

        with self._lock:
            bundles = list(self._bundles.values())

        for bundle in bundles:
            # Tenant scoping: skip bundles that don't match the tenant
            if tenant_id is not None:
                bundle_tenant = bundle._policies  # noqa: SLF001
                # Check if any policy in the bundle has tenant metadata
                tenant_scoped = False
                for policy in bundle_tenant.values():
                    policy_tenant = policy.metadata.get("tenant_id")
                    if policy_tenant is not None and policy_tenant != tenant_id:
                        tenant_scoped = True
                        break
                if tenant_scoped:
                    continue

            decision = bundle.evaluate(input_doc)
            all_matched.extend(decision.matched_rules)
            if decision.denied:
                any_denied = True
                deny_reasons.append(decision.reason)
            elif decision.allowed:
                any_allowed = True

        if any_denied:
            effect = DecisionEffect.DENY
            reason = "; ".join(deny_reasons)
        elif any_allowed:
            effect = DecisionEffect.ALLOW
            reason = "allowed by policy engine"
        else:
            if self._default_deny:
                effect = DecisionEffect.DENY
                reason = "no matching policies (fail-closed)"
            else:
                effect = DecisionEffect.ALLOW
                reason = "no matching policies (fail-open)"

        return PolicyDecision(
            policy_name="PolicyEngine",
            effect=effect,
            matched_rules=tuple(all_matched),
            input_summary=_summarize_input(input_doc),
            reason=reason,
        )

    def evaluate_for_authorization(
        self,
        ctx: AuthorizationContext,
    ) -> PolicyDecision:
        """Evaluate policies using an AuthorizationContext.

        This converts the AuthorizationContext into an input document
        and evaluates it against all registered bundles.
        """
        input_doc = {
            "subject": ctx.subject,
            "resource": ctx.resource,
            "action": ctx.action,
            "environment": ctx.environment,
            "tenant_id": ctx.tenant_id,
        }
        return self.evaluate(input_doc, tenant_id=ctx.tenant_id)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the engine configuration to a dictionary."""
        return {
            "bundles": [b.to_dict() for b in self._bundles.values()],
            "default_deny": self._default_deny,
        }


# ---------------------------------------------------------------------------
# RegoParser
# ---------------------------------------------------------------------------


class RegoParser:
    """Parser for Rego-like policy documents.

    This parser converts Rego-style policy documents into :class:`Policy`
    objects. It supports a subset of the Rego language:

    - ``package`` declarations
    - ``allow`` and ``deny`` rules
    - ``import`` statements (for documentation)
    - Comments (``#``)

    Example Rego document::

        package dcc.security.authz

        import future.keywords.in

        default allow := false

        allow if {
            input.action == "read"
            input.resource.type == "asset"
        }

        deny if {
            input.resource.criticality == "critical"
            not input.environment.mfa_verified
        }

    The parser produces a :class:`Policy` with the corresponding rules.
    """

    # Regex patterns for parsing
    _PACKAGE_RE = re.compile(r"^package\s+([\w.]+)", re.MULTILINE)
    _DEFAULT_RE = re.compile(r"^default\s+(allow|deny)\s*:=\s*(true|false)", re.MULTILINE)
    _RULE_RE = re.compile(
        r"^(allow|deny)\s+if\s*\{(.*?)\}",
        re.MULTILINE | re.DOTALL,
    )
    _COMMENT_RE = re.compile(r"#.*$", re.MULTILINE)
    _IMPORT_RE = re.compile(r"^import\s+([\w.]+)", re.MULTILINE)

    def parse(self, document: str) -> Policy:
        """Parse a Rego document into a :class:`Policy`.

        Parameters
        ----------
        document:
            The Rego policy document as a string.

        Returns
        -------
        Policy
            The parsed policy.

        Raises
        ------
        PolicySyntaxError
            If the document has syntax errors.
        """
        # Strip comments
        cleaned = self._COMMENT_RE.sub("", document)

        # Extract package name
        pkg_match = self._PACKAGE_RE.search(cleaned)
        if not pkg_match:
            raise PolicySyntaxError("Rego document must have a package declaration")
        package_name = pkg_match.group(1)

        # Extract default decision
        default_match = self._DEFAULT_RE.search(cleaned)
        default_allow = False
        if default_match:
            default_allow = default_match.group(2) == "true"

        # Extract rules
        rules: list[Rule] = []
        for match in self._RULE_RE.finditer(cleaned):
            effect_str = match.group(1)
            body = match.group(2).strip()

            effect = Effect.ALLOW if effect_str == "allow" else Effect.DENY

            # Convert Rego body to Python condition
            condition = self._rego_body_to_condition(body)

            rule_name = f"{effect_str}-{len(rules) + 1}"
            rules.append(
                Rule(
                    name=rule_name,
                    effect=effect,
                    condition=condition,
                    description=f"Parsed from Rego: {effect_str} if {{ {body} }}",
                )
            )

        # If no explicit rules but a default is set, add a default rule
        if not rules and default_allow:
            rules.append(
                Rule(
                    name="default-allow",
                    effect=Effect.ALLOW,
                    condition="true",
                    description="Default allow",
                )
            )
        elif not rules and not default_allow:
            rules.append(
                Rule(
                    name="default-deny",
                    effect=Effect.DENY,
                    condition="true",
                    description="Default deny",
                )
            )

        return Policy(
            name=package_name,
            description=f"Parsed from Rego package {package_name}",
            rules=rules,
            metadata={"source": "rego", "package": package_name},
        )

    def parse_file(self, path: str | Path) -> Policy:
        """Parse a Rego document from a file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Policy file not found: {path}")
        return self.parse(path.read_text(encoding="utf-8"))

    def _rego_body_to_condition(self, body: str) -> str:
        """Convert a Rego rule body to a Python condition expression.

        This handles common Rego patterns:
        - ``input.field == "value"`` → ``input.field == "value"``
        - ``not input.field`` → ``not input.field``
        - ``input.field in ["a", "b"]`` → ``input.field in ["a", "b"]``
        - ``input.field`` → ``input.field``
        - Multi-line bodies are joined with ``and``
        """
        # The body is already close to Python syntax for simple cases.
        # We just need to handle Rego-specific keywords.
        condition = body.strip()

        # Multi-line bodies: join lines with 'and'
        lines = [line.strip() for line in condition.split('\n') if line.strip()]
        if len(lines) > 1:
            condition = ' and '.join(lines)
        else:
            condition = lines[0] if lines else condition

        # Replace Rego's `contains` with Python's `in` for strings
        # e.g., `input.name contains "test"` → `"test" in input.name`
        condition = re.sub(
            r"(\w+(?:\.\w+)*)\s+contains\s+(\w+(?:\.\w+)*)",
            r"\2 in \1",
            condition,
        )

        # Replace Rego's `startswith` with Python's `.startswith()`
        condition = re.sub(
            r"(\w+(?:\.\w+)*)\s+startswith\s+(\w+(?:\.\w+)*)",
            r"\1.startswith(\2)",
            condition,
        )

        # Replace Rego's `endswith` with Python's `.endswith()`
        condition = re.sub(
            r"(\w+(?:\.\w+)*)\s+endswith\s+(\w+(?:\.\w+)*)",
            r"\1.endswith(\2)",
            condition,
        )

        return condition


# ---------------------------------------------------------------------------
# PolicyValidator
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Built-in policy templates
# ---------------------------------------------------------------------------


def create_default_policy_bundle() -> PolicyBundle:
    """Create a policy bundle with sensible default security policies.

    Returns
    -------
    PolicyBundle
        A bundle with policies for:
        - MFA requirement for critical resources
        - Business hours restriction
        - Tenant isolation
        - Read-only access for viewers
    """
    policies = [
        Policy(
            name="require-mfa-for-critical",
            description="Require MFA for access to critical resources",
            rules=[
                Rule(
                    name="deny-critical-without-mfa",
                    effect=Effect.DENY,
                    condition="input.resource.criticality == 'critical' and not input.environment.mfa_verified",
                    description="Deny access to critical resources without MFA",
                ),
                Rule(
                    name="allow-critical-with-mfa",
                    effect=Effect.ALLOW,
                    condition="input.resource.criticality == 'critical' and input.environment.mfa_verified",
                    description="Allow access to critical resources with MFA",
                ),
            ],
        ),
        Policy(
            name="business-hours-restriction",
            description="Restrict write operations to business hours",
            rules=[
                Rule(
                    name="deny-write-outside-business-hours",
                    effect=Effect.DENY,
                    condition="input.action in ['write', 'delete', 'execute'] and not input.environment.business_hours",
                    description="Deny write/delete/execute outside business hours",
                ),
            ],
        ),
        Policy(
            name="tenant-isolation",
            description="Enforce tenant data isolation",
            rules=[
                Rule(
                    name="deny-cross-tenant-access",
                    effect=Effect.DENY,
                    condition="input.resource.tenant_id is not None and input.resource.tenant_id != input.tenant_id",
                    description="Deny access to resources belonging to other tenants",
                ),
            ],
        ),
        Policy(
            name="viewer-read-only",
            description="Viewers can only read",
            rules=[
                Rule(
                    name="allow-viewer-read",
                    effect=Effect.ALLOW,
                    condition="'viewer' in input.subject.roles and input.action in ['read', 'list', 'get', 'view']",
                    description="Allow viewers to read",
                ),
                Rule(
                    name="deny-viewer-write",
                    effect=Effect.DENY,
                    condition="'viewer' in input.subject.roles and input.action in ['write', 'delete', 'execute']",
                    description="Deny viewers from writing",
                ),
            ],
        ),
    ]

    return PolicyBundle(
        name="default-security-policies",
        description="Default security policies for Data Center Commander",
        policies=policies,
    )


def create_default_policy_engine() -> PolicyEngine:
    """Create a policy engine pre-populated with default security policies.

    Returns
    -------
    PolicyEngine
        An engine with the default policy bundle registered.
    """
    return PolicyEngine(bundles=[create_default_policy_bundle()])


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


# ---------------------------------------------------------------------------
# Policy-as-code DSL: JSON/YAML policy document support
# ---------------------------------------------------------------------------


class PolicyDocument:
    """A policy document that can be loaded from JSON or YAML.

    This provides a declarative way to define policies without writing
    Python code. The document format is JSON or YAML with the following
    structure::

        {
            "name": "my-policy",
            "description": "A custom security policy",
            "version": "1.0.0",
            "metadata": {"team": "security"},
            "rules": [
                {
                    "name": "deny-insecure",
                    "effect": "deny",
                    "condition": "input.environment.secure == false",
                    "description": "Deny insecure requests"
                }
            ]
        }
    """

    @classmethod
    def from_json(cls, json_str: str) -> Policy:
        """Create a policy from a JSON string."""
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise PolicySyntaxError(f"Invalid JSON: {exc}") from exc
        return Policy.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Policy:
        """Create a policy from a dictionary."""
        return Policy.from_dict(data)

    @classmethod
    def from_file(cls, path: str | Path) -> Policy:
        """Load a policy from a JSON or YAML file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Policy file not found: {path}")

        content = path.read_text(encoding="utf-8")

        if path.suffix in (".yaml", ".yml"):
            try:
                import yaml  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "PyYAML is required to load YAML policy files. "
                    "Install it with: pip install pyyaml"
                ) from exc
            try:
                data = yaml.safe_load(content)
            except yaml.YAMLError as exc:
                raise PolicySyntaxError(f"Invalid YAML: {exc}") from exc
        else:
            try:
                data = json.loads(content)
            except json.JSONDecodeError as exc:
                raise PolicySyntaxError(f"Invalid JSON: {exc}") from exc

        return Policy.from_dict(data)


# ---------------------------------------------------------------------------
# Integration with existing authz system
# ---------------------------------------------------------------------------


class PolicyAuthzBridge:
    """Bridge between the policy engine and the existing authz system.

    This allows the policy engine to be used as a drop-in replacement
    or complement to the existing :class:`~dcc.security.authz.Authorizer`.

    Usage::

        from dcc.security.policy import PolicyAuthzBridge, create_default_policy_engine

        bridge = PolicyAuthzBridge(create_default_policy_engine())

        # Use like the existing Authorizer
        allowed = bridge.can(
            subject_roles=["viewer"],
            action="read",
            resource={"type": "asset", "tenant_id": tid},
        )
    """

    def __init__(self, engine: PolicyEngine) -> None:
        self._engine = engine

    def can(
        self,
        subject_roles: Iterable[str],
        action: str,
        resource: str | dict[str, Any],
        *,
        subject: dict[str, Any] | None = None,
        environment: dict[str, Any] | None = None,
        tenant_id: str | None = None,
    ) -> bool:
        """Check whether the subject can perform the action on the resource.

        This mirrors the interface of :meth:`~dcc.security.authz.Authorizer.can`.
        """
        # Build input document
        subject_attrs: dict[str, Any] = {"roles": list(subject_roles)}
        if subject:
            subject_attrs.update(subject)

        if isinstance(resource, str):
            resource_attrs: dict[str, Any] = {"type": resource}
        else:
            resource_attrs = dict(resource)

        input_doc = {
            "subject": subject_attrs,
            "resource": resource_attrs,
            "action": action,
            "environment": dict(environment or {}),
            "tenant_id": tenant_id,
        }

        decision = self._engine.evaluate(input_doc, tenant_id=tenant_id)
        return decision.allowed

    def authorize(
        self,
        subject_roles: Iterable[str],
        action: str,
        resource: str | dict[str, Any],
        *,
        subject: dict[str, Any] | None = None,
        environment: dict[str, Any] | None = None,
        tenant_id: str | None = None,
    ) -> None:
        """Like :meth:`can` but raises on denial.

        Raises
        ------
        PermissionError
            If access is denied.
        """
        if not self.can(
            subject_roles,
            action,
            resource,
            subject=subject,
            environment=environment,
            tenant_id=tenant_id,
        ):
            raise PermissionError(
                f"access denied: {action} on {resource}"
            )
