"""Launch template manager for AWS Auto Scaling.

Provides CRUD operations for launch templates with validation,
versioning, and tag management. All operations are advisory and
read-only against the AWS API unless explicitly permitted.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .models import LaunchTemplate, LaunchTemplateSpecification

# Validation patterns
NAME_RE = re.compile(r"^[A-Za-z0-9._/-]{1,128}$")
IMAGE_ID_RE = re.compile(r"^ami-[0-9a-f]{8,17}$")
INSTANCE_TYPE_RE = re.compile(r"^[a-z][a-z0-9]*\.[a-z0-9]+$")
SG_ID_RE = re.compile(r"^sg-[0-9a-f]{8,17}$")
MAX_USER_DATA_BYTES = 16384  # 16 KiB


class LaunchTemplateError(Exception):
    """Base exception for launch template operations."""


class LaunchTemplateNotFoundError(LaunchTemplateError):
    """Raised when a launch template is not found."""


class LaunchTemplateValidationError(LaunchTemplateError):
    """Raised when launch template validation fails."""


class LaunchTemplateManager:
    """Manages AWS launch templates."""

    def __init__(self) -> None:
        self._templates: dict[str, LaunchTemplate] = {}

    def create(
        self,
        *,
        name: str,
        image_id: str,
        instance_type: str,
        key_name: str = "",
        security_group_ids: list[str] | None = None,
        user_data: str = "",
        iam_instance_profile: str = "",
        block_device_mappings: list[dict[str, Any]] | None = None,
        network_interfaces: list[dict[str, Any]] | None = None,
        tags: dict[str, str] | None = None,
        metadata_options: dict[str, Any] | None = None,
        monitoring_enabled: bool = False,
        ebs_optimized: bool = False,
        description: str = "",
    ) -> LaunchTemplate:
        """Create a new launch template.

        Args:
            name: Template name (1-128 chars, alphanumeric plus . _ / -).
            image_id: AMI ID (ami-xxxxxxxx or ami-xxxxxxxxxxxxxxxxx).
            instance_type: EC2 instance type (e.g., m5.large).
            key_name: SSH key pair name.
            security_group_ids: List of security group IDs.
            user_data: Base64-encoded user data script (max 16 KiB).
            iam_instance_profile: IAM instance profile ARN or name.
            block_device_mappings: Block device mapping configurations.
            network_interfaces: Network interface configurations.
            tags: Resource tags.
            metadata_options: Instance metadata options (IMDSv2, etc.).
            monitoring_enabled: Enable detailed CloudWatch monitoring.
            ebs_optimized: Enable EBS optimization.
            description: Template description.

        Returns:
            The created LaunchTemplate.

        Raises:
            LaunchTemplateValidationError: If validation fails.
        """
        self._validate_name(name)
        self._validate_image_id(image_id)
        self._validate_instance_type(instance_type)
        self._validate_security_groups(security_group_ids or [])
        self._validate_user_data(user_data)

        template_id = self._generate_template_id(name)
        template = LaunchTemplate(
            launch_template_id=template_id,
            name=name,
            version=1,
            image_id=image_id,
            instance_type=instance_type,
            key_name=key_name,
            security_group_ids=list(security_group_ids or []),
            user_data=user_data,
            iam_instance_profile=iam_instance_profile,
            block_device_mappings=list(block_device_mappings or []),
            network_interfaces=list(network_interfaces or []),
            tags=dict(tags or {}),
            metadata_options=dict(metadata_options or {}),
            monitoring_enabled=monitoring_enabled,
            ebs_optimized=ebs_optimized,
            description=description,
        )
        self._templates[template_id] = template
        return template

    def get(self, template_id: str) -> LaunchTemplate:
        """Get a launch template by ID.

        Raises:
            LaunchTemplateNotFoundError: If template not found.
        """
        template = self._templates.get(template_id)
        if template is None:
            raise LaunchTemplateNotFoundError(f"Launch template not found: {template_id}")
        return template

    def list_templates(
        self,
        *,
        name_prefix: str = "",
        tags: dict[str, str] | None = None,
    ) -> list[LaunchTemplate]:
        """List launch templates, optionally filtered by name prefix and tags."""
        results = list(self._templates.values())
        if name_prefix:
            results = [t for t in results if t.name.startswith(name_prefix)]
        if tags:
            results = [
                t for t in results
                if all(t.tags.get(k) == v for k, v in tags.items())
            ]
        return sorted(results, key=lambda t: t.name)

    def update(
        self,
        template_id: str,
        *,
        image_id: str | None = None,
        instance_type: str | None = None,
        key_name: str | None = None,
        security_group_ids: list[str] | None = None,
        user_data: str | None = None,
        tags: dict[str, str] | None = None,
        monitoring_enabled: bool | None = None,
        ebs_optimized: bool | None = None,
    ) -> LaunchTemplate:
        """Update a launch template, creating a new version.

        Returns:
            The updated LaunchTemplate with incremented version.

        Raises:
            LaunchTemplateNotFoundError: If template not found.
            LaunchTemplateValidationError: If validation fails.
        """
        old = self.get(template_id)

        if image_id is not None:
            self._validate_image_id(image_id)
        if instance_type is not None:
            self._validate_instance_type(instance_type)
        if security_group_ids is not None:
            self._validate_security_groups(security_group_ids)
        if user_data is not None:
            self._validate_user_data(user_data)

        new_version = old.version + 1
        updated = LaunchTemplate(
            launch_template_id=old.launch_template_id,
            name=old.name,
            version=new_version,
            image_id=image_id if image_id is not None else old.image_id,
            instance_type=instance_type if instance_type is not None else old.instance_type,
            key_name=key_name if key_name is not None else old.key_name,
            security_group_ids=(
                security_group_ids if security_group_ids is not None else old.security_group_ids
            ),
            user_data=user_data if user_data is not None else old.user_data,
            iam_instance_profile=old.iam_instance_profile,
            block_device_mappings=old.block_device_mappings,
            network_interfaces=old.network_interfaces,
            tags=tags if tags is not None else old.tags,
            metadata_options=old.metadata_options,
            monitoring_enabled=(
                monitoring_enabled if monitoring_enabled is not None else old.monitoring_enabled
            ),
            ebs_optimized=ebs_optimized if ebs_optimized is not None else old.ebs_optimized,
            created_at=old.created_at,
            description=old.description,
        )
        self._templates[template_id] = updated
        return updated

    def delete(self, template_id: str) -> bool:
        """Delete a launch template. Returns True if it existed."""
        return self._templates.pop(template_id, None) is not None

    def get_specification(
        self,
        template_id: str,
        version: str = "$Latest",
    ) -> LaunchTemplateSpecification:
        """Get a launch template specification for use in an ASG.

        Args:
            template_id: The launch template ID.
            version: Version number, "$Latest", or "$Default".

        Returns:
            LaunchTemplateSpecification for ASG attachment.
        """
        template = self.get(template_id)
        if version == "$Latest":
            resolved = str(template.version)
        elif version == "$Default":
            resolved = "1"
        else:
            resolved = version
        return LaunchTemplateSpecification(
            launch_template_id=template_id,
            version=resolved,
        )

    def clone(
        self,
        template_id: str,
        *,
        new_name: str,
        description: str = "",
    ) -> LaunchTemplate:
        """Clone an existing launch template with a new name.

        Returns:
            The cloned LaunchTemplate.
        """
        old = self.get(template_id)
        self._validate_name(new_name)
        clone_id = self._generate_template_id(new_name)
        cloned = LaunchTemplate(
            launch_template_id=clone_id,
            name=new_name,
            version=1,
            image_id=old.image_id,
            instance_type=old.instance_type,
            key_name=old.key_name,
            security_group_ids=list(old.security_group_ids),
            user_data=old.user_data,
            iam_instance_profile=old.iam_instance_profile,
            block_device_mappings=list(old.block_device_mappings),
            network_interfaces=list(old.network_interfaces),
            tags=dict(old.tags),
            metadata_options=dict(old.metadata_options),
            monitoring_enabled=old.monitoring_enabled,
            ebs_optimized=old.ebs_optimized,
            description=description or f"Cloned from {old.name}",
        )
        self._templates[clone_id] = cloned
        return cloned

    # -- Validation helpers --

    def _validate_name(self, name: str) -> None:
        if not name or not NAME_RE.fullmatch(name):
            raise LaunchTemplateValidationError(
                f"Invalid launch template name: {name!r}. Must be 1-128 chars, "
                "alphanumeric plus . _ / -"
            )

    def _validate_image_id(self, image_id: str) -> None:
        if not image_id or not IMAGE_ID_RE.fullmatch(image_id):
            raise LaunchTemplateValidationError(
                f"Invalid AMI ID: {image_id!r}. Must match ami-xxxxxxxx or ami-xxxxxxxxxxxxxxxxx"
            )

    def _validate_instance_type(self, instance_type: str) -> None:
        if not instance_type or not INSTANCE_TYPE_RE.fullmatch(instance_type):
            raise LaunchTemplateValidationError(
                f"Invalid instance type: {instance_type!r}. Must match pattern like m5.large"
            )

    def _validate_security_groups(self, sg_ids: list[str]) -> None:
        for sg_id in sg_ids:
            if not SG_ID_RE.fullmatch(sg_id):
                raise LaunchTemplateValidationError(
                    f"Invalid security group ID: {sg_id!r}. Must match sg-xxxxxxxx"
                )

    def _validate_user_data(self, user_data: str) -> None:
        if len(user_data.encode("utf-8")) > MAX_USER_DATA_BYTES:
            raise LaunchTemplateValidationError(
                f"User data exceeds {MAX_USER_DATA_BYTES} bytes"
            )

    def _generate_template_id(self, name: str) -> str:
        """Generate a deterministic template ID from name and timestamp."""
        import hashlib
        ts = datetime.now(timezone.utc).isoformat()
        digest = hashlib.sha256(f"{name}:{ts}".encode()).hexdigest()[:17]
        return f"lt-{digest}"
