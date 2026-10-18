"""Sentinel integration for the policy-as-code engine.

This module provides a parser for HashiCorp Sentinel policy documents,
allowing policies to be written in the Sentinel language and evaluated
by the policy engine.

Sentinel is HashiCorp's policy-as-code language, commonly used with
Terraform Cloud/Enterprise. This parser supports a practical subset:

- ``main`` rule with ``true``/``false`` return
- ``import`` statements (for documentation)
- Comments (``#`` and ``//``)
- Common Sentinel expressions

Example Sentinel document::

    import "tfplan"

    main = rule {
        all tfplan.resources as _, instances {
            all instances as r {
                r.applied.tags["environment"] is not "production" or
                r.applied.sku is not "premium"
            }
        }
    }
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .errors import PolicySyntaxError
from .types import Effect, Policy, Rule

__all__ = ["SentinelParser"]


class SentinelParser:
    """Parser for Sentinel-like policy documents.

    This parser converts Sentinel-style policy documents into :class:`Policy`
    objects. It supports a subset of the Sentinel language suitable for
    data-center infrastructure policies.
    """

    _MAIN_RULE_RE = re.compile(
        r"main\s*=\s*rule\s*\{(.*?)\}",
        re.MULTILINE | re.DOTALL,
    )
    _COMMENT_RE = re.compile(r"(#|//).*$", re.MULTILINE)
    _IMPORT_RE = re.compile(r"^import\s+\"([\w.]+)\"", re.MULTILINE)

    def parse(self, document: str) -> Policy:
        """Parse a Sentinel document into a :class:`Policy`.

        Parameters
        ----------
        document:
            The Sentinel policy document as a string.

        Returns
        -------
        Policy
            The parsed policy.

        Raises
        ------
        PolicySyntaxError
            If the document has syntax errors.
        """
        cleaned = self._COMMENT_RE.sub("", document)

        main_match = self._MAIN_RULE_RE.search(cleaned)
        if not main_match:
            raise PolicySyntaxError(
                "Sentinel document must have a 'main = rule { ... }' declaration"
            )

        body = main_match.group(1).strip()
        condition = self._sentinel_body_to_condition(body)

        rules: list[Rule] = [
            Rule(
                name="main",
                effect=Effect.ALLOW,
                condition=condition,
                description="Parsed from Sentinel: main rule",
            )
        ]

        return Policy(
            name="sentinel-policy",
            description="Parsed from Sentinel policy",
            rules=rules,
            metadata={"source": "sentinel"},
        )

    def parse_file(self, path: str | Path) -> Policy:
        """Parse a Sentinel document from a file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Policy file not found: {path}")
        return self.parse(path.read_text(encoding="utf-8"))

    def _sentinel_body_to_condition(self, body: str) -> str:
        """Convert a Sentinel rule body to a Python condition expression.

        This handles common Sentinel patterns:
        - ``true`` → ``true``
        - ``false`` → ``false``
        - ``x is not "value"`` → ``x != "value"``
        - ``x is "value"`` → ``x == "value"``
        - ``x and y`` → ``x and y``
        - ``x or y`` → ``x or y``
        - ``not x`` → ``not x``
        """
        condition = body.strip()

        # Replace Sentinel's `is` with Python's `==`
        condition = re.sub(r"\bis\s+not\b", "!=", condition)
        condition = re.sub(r"\bis\b", "==", condition)

        # Replace Sentinel's `is not` with Python's `!=`
        # (already handled above, but double-check)

        return condition
