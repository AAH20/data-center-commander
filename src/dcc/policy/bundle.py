"""Policy bundle management for the policy-as-code engine.

This module provides utilities for creating, loading, and managing
policy bundles — collections of related policies that are evaluated
together.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .types import Effect, Policy, PolicyBundle, Rule

__all__ = [
    "PolicyBundle",
    "create_default_policy_bundle",
    "load_bundle_from_directory",
    "load_bundle_from_file",
]


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


def load_bundle_from_directory(
    directory: str | Path,
    *,
    bundle_name: str | None = None,
) -> PolicyBundle:
    """Load a policy bundle from a directory of JSON policy files.

    Each ``.json`` file in the directory is loaded as a policy and added
    to the bundle.

    Parameters
    ----------
    directory:
        Path to the directory containing policy JSON files.
    bundle_name:
        Optional name for the bundle. Defaults to the directory name.

    Returns
    -------
    PolicyBundle
        The loaded policy bundle.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    name = bundle_name or directory.name
    policies: list[Policy] = []

    for file_path in sorted(directory.glob("*.json")):
        policy = _load_policy_from_json(file_path)
        policies.append(policy)

    return PolicyBundle(
        name=name,
        description=f"Loaded from directory: {directory}",
        policies=policies,
    )


def load_bundle_from_file(
    path: str | Path,
    *,
    bundle_name: str | None = None,
) -> PolicyBundle:
    """Load a policy bundle from a JSON file.

    The file should contain either a single policy or a bundle definition
    with a ``policies`` array.

    Parameters
    ----------
    path:
        Path to the JSON file.
    bundle_name:
        Optional name for the bundle. Defaults to the file name.

    Returns
    -------
    PolicyBundle
        The loaded policy bundle.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Policy file not found: {path}")

    name = bundle_name or path.stem
    data = json.loads(path.read_text(encoding="utf-8"))

    if "policies" in data:
        policies = [Policy.from_dict(p) for p in data["policies"]]
        return PolicyBundle(
            name=data.get("name", name),
            description=data.get("description", ""),
            policies=policies,
        )
    else:
        policy = Policy.from_dict(data)
        return PolicyBundle(
            name=name,
            description=f"Loaded from file: {path}",
            policies=[policy],
        )


def _load_policy_from_json(path: Path) -> Policy:
    """Load a single policy from a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return Policy.from_dict(data)
