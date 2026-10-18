"""Policy evaluation engine.

The PolicyEngine is the main entry point for policy evaluation. It maintains
a registry of policy bundles and evaluates them against input documents.

Features:
- Adding/removing policy bundles
- Evaluating input documents against all registered bundles
- Tenant-scoped policy evaluation
- Configurable default-deny behavior
- Thread-safe operations
"""
from __future__ import annotations

import threading
from typing import Any, Iterable, Mapping

from .types import DecisionEffect, PolicyBundle, PolicyDecision

__all__ = ["PolicyEngine"]


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
        all_matched: list[str] = []
        any_denied = False
        any_allowed = False
        deny_reasons: list[str] = []

        with self._lock:
            bundles = list(self._bundles.values())

        for bundle in bundles:
            if tenant_id is not None:
                bundle_tenant = bundle._policies  # noqa: SLF001
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

    def to_dict(self) -> dict[str, Any]:
        """Serialize the engine configuration to a dictionary."""
        return {
            "bundles": [b.to_dict() for b in self._bundles.values()],
            "default_deny": self._default_deny,
        }


def _summarize_input(input_doc: dict[str, Any], max_len: int = 200) -> str:
    """Create a short summary of the input document for auditing."""
    import json

    try:
        summary = json.dumps(input_doc, default=str, sort_keys=True)
    except (TypeError, ValueError):
        summary = str(input_doc)
    if len(summary) > max_len:
        summary = summary[: max_len - 3] + "..."
    return summary
