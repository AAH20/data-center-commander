"""OPA/Rego integration for the policy-as-code engine.

This module provides a parser for Rego policy documents, allowing policies
to be written in the Open Policy Agent (OPA) Rego language and evaluated
by the policy engine.

The parser supports a practical subset of Rego:

- ``package`` declarations
- ``allow`` and ``deny`` rules with ``if`` conditions
- ``default`` decisions
- ``import`` statements (for documentation)
- Comments (``#``)
- Multi-line rule bodies
- Common Rego operators: ``==``, ``!=``, ``in``, ``not``, ``contains``,
  ``startswith``, ``endswith``

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
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .errors import PolicySyntaxError
from .types import Effect, Policy, Rule

__all__ = ["RegoParser"]


class RegoParser:
    """Parser for Rego-like policy documents.

    This parser converts Rego-style policy documents into :class:`Policy`
    objects. It supports a subset of the Rego language suitable for
    data-center security policies.
    """

    _PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)", re.MULTILINE)
    _DEFAULT_RE = re.compile(r"^\s*default\s+(allow|deny)\s*:=\s*(true|false)", re.MULTILINE)
    _RULE_RE = re.compile(
        r"^\s*(allow|deny)\s+if\s*\{(.*?)\}",
        re.MULTILINE | re.DOTALL,
    )
    _COMMENT_RE = re.compile(r"#.*$", re.MULTILINE)
    _IMPORT_RE = re.compile(r"^\s*import\s+([\w.]+)", re.MULTILINE)

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
        cleaned = self._COMMENT_RE.sub("", document)

        pkg_match = self._PACKAGE_RE.search(cleaned)
        if not pkg_match:
            raise PolicySyntaxError("Rego document must have a package declaration")
        package_name = pkg_match.group(1)

        default_match = self._DEFAULT_RE.search(cleaned)
        default_allow = False
        if default_match:
            default_allow = default_match.group(2) == "true"

        rules: list[Rule] = []
        for match in self._RULE_RE.finditer(cleaned):
            effect_str = match.group(1)
            body = match.group(2).strip()

            effect = Effect.ALLOW if effect_str == "allow" else Effect.DENY
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
        condition = body.strip()

        lines = [line.strip() for line in condition.split("\n") if line.strip()]
        if len(lines) > 1:
            condition = " and ".join(lines)
        else:
            condition = lines[0] if lines else condition

        # Replace Rego's `contains` with Python's `in` for strings
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

        # Replace Rego's array iteration `arr[_] == value` with `value in arr`
        # Handles both bare identifiers and quoted strings
        condition = re.sub(
            r"(\w+(?:\.\w+)*)\s*\[_\]\s*==\s*(\"[^\"]*\"|'[^']*'|\w+(?:\.\w+)*)",
            r"\2 in \1",
            condition,
        )

        # Replace Rego's array iteration `arr[_] != value` with `value not in arr`
        condition = re.sub(
            r"(\w+(?:\.\w+)*)\s*\[_\]\s*!=\s*(\"[^\"]*\"|'[^']*'|\w+(?:\.\w+)*)",
            r"\2 not in \1",
            condition,
        )

        return condition
