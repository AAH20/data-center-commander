"""Policy document loading for the policy-as-code engine.

This module provides a declarative way to define policies without writing
Python code. Policies can be loaded from JSON or YAML files.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import PolicySyntaxError
from .types import Policy

__all__ = ["PolicyDocument"]


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
