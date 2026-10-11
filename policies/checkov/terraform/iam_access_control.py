"""
Checkov Custom Policies — IAM & Access Control for Data Center IaC
Covers: IAM policies, MFA, password policies, role trust, least privilege
"""

from checkov.common.models.enums import CheckCategories, CheckResult
from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck


class IAMPolicyNotWildcard(BaseResourceCheck):
    """Ensure IAM policies do not use wildcard actions."""

    def __init__(self):
        name = "Ensure IAM policies do not use wildcard actions"
        id = "DC_IAM_001"
        supported_resources = [
            "aws_iam_policy",
            "aws_iam_role_policy",
            "aws_iam_group_policy",
            "aws_iam_user_policy",
        ]
        categories = [CheckCategories.IAM]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        policy = conf.get("policy", "")
        if isinstance(policy, list):
            policy = policy[0] if policy else ""
        if isinstance(policy, str):
            if (
                '"Action": "*"' in policy
                or '"Action":["*"]' in policy
                or '"Action": ["*"]' in policy
            ):
                return CheckResult.FAILED
        return CheckResult.PASSED


class IAMRoleTrustPolicyNotWildcard(BaseResourceCheck):
    """Ensure IAM role trust policies do not allow wildcard principals."""

    def __init__(self):
        name = "Ensure IAM role trust policies do not allow wildcard principals"
        id = "DC_IAM_002"
        supported_resources = ["aws_iam_role"]
        categories = [CheckCategories.IAM]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        assume_role_policy = conf.get("assume_role_policy", "")
        if isinstance(assume_role_policy, list):
            assume_role_policy = assume_role_policy[0] if assume_role_policy else ""
        if isinstance(assume_role_policy, str):
            if (
                '"Principal": "*"' in assume_role_policy
                or '"Principal":{"AWS":"*"}' in assume_role_policy
            ):
                return CheckResult.FAILED
        return CheckResult.PASSED


class IAMUserHasMFA(BaseResourceCheck):
    """Ensure IAM users have MFA enabled (via virtual MFA device)."""

    def __init__(self):
        name = "Ensure IAM users have MFA enabled"
        id = "DC_IAM_003"
        supported_resources = ["aws_iam_virtual_mfa_device"]
        categories = [CheckCategories.IAM]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        # If a virtual MFA device exists, MFA is being used
        user_name = conf.get("user_name", "")
        if isinstance(user_name, list):
            user_name = user_name[0] if user_name else ""
        if user_name:
            return CheckResult.PASSED
        return CheckResult.FAILED


class IAMPasswordPolicyStrong(BaseResourceCheck):
    """Ensure IAM password policy requires strong passwords."""

    def __init__(self):
        name = "Ensure IAM password policy requires strong passwords"
        id = "DC_IAM_004"
        supported_resources = ["aws_iam_account_password_policy"]
        categories = [CheckCategories.IAM]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        minimum_password_length = conf.get("minimum_password_length", 6)
        if isinstance(minimum_password_length, list):
            minimum_password_length = minimum_password_length[0] if minimum_password_length else 6
        require_symbols = conf.get("require_symbols", False)
        if isinstance(require_symbols, list):
            require_symbols = require_symbols[0] if require_symbols else False
        require_numbers = conf.get("require_numbers", False)
        if isinstance(require_numbers, list):
            require_numbers = require_numbers[0] if require_numbers else False
        require_uppercase = conf.get("require_uppercase_characters", False)
        if isinstance(require_uppercase, list):
            require_uppercase = require_uppercase[0] if require_uppercase else False
        require_lowercase = conf.get("require_lowercase_characters", False)
        if isinstance(require_lowercase, list):
            require_lowercase = require_lowercase[0] if require_lowercase else False
        if minimum_password_length < 14:
            return CheckResult.FAILED
        if not all([require_symbols, require_numbers, require_uppercase, require_lowercase]):
            return CheckResult.FAILED
        return CheckResult.PASSED


class IAMRoleHasDescription(BaseResourceCheck):
    """Ensure IAM roles have a description."""

    def __init__(self):
        name = "Ensure IAM roles have a description"
        id = "DC_IAM_005"
        supported_resources = ["aws_iam_role"]
        categories = [CheckCategories.IAM]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        description = conf.get("description", "")
        if isinstance(description, list):
            description = description[0] if description else ""
        if not description or description.strip() == "":
            return CheckResult.FAILED
        return CheckResult.PASSED


class IAMGroupHasUsers(BaseResourceCheck):
    """Ensure IAM groups have at least one user assigned."""

    def __init__(self):
        name = "Ensure IAM groups have at least one user assigned"
        id = "DC_IAM_006"
        supported_resources = ["aws_iam_group_membership"]
        categories = [CheckCategories.IAM]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        users = conf.get("users", [])
        if isinstance(users, list) and len(users) > 0:
            return CheckResult.PASSED
        return CheckResult.FAILED


class IAMPolicyAttachedToGroupOrRole(BaseResourceCheck):
    """Ensure IAM policies are attached to groups or roles, not directly to users."""

    def __init__(self):
        name = "Ensure IAM policies are attached to groups or roles"
        id = "DC_IAM_007"
        supported_resources = ["aws_iam_user_policy_attachment"]
        categories = [CheckCategories.IAM]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        # This check flags direct user policy attachments
        return CheckResult.FAILED


class IAMNoAdminAccessPolicy(BaseResourceCheck):
    """Ensure no IAM policies grant AdministratorAccess."""

    def __init__(self):
        name = "Ensure no IAM policies grant AdministratorAccess"
        id = "DC_IAM_008"
        supported_resources = [
            "aws_iam_policy",
            "aws_iam_role_policy",
            "aws_iam_group_policy",
            "aws_iam_user_policy",
        ]
        categories = [CheckCategories.IAM]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        policy = conf.get("policy", "")
        if isinstance(policy, list):
            policy = policy[0] if policy else ""
        if isinstance(policy, str):
            if "AdministratorAccess" in policy:
                return CheckResult.FAILED
        return CheckResult.PASSED


class IAMRoleMaxSessionDuration(BaseResourceCheck):
    """Ensure IAM roles have a maximum session duration set."""

    def __init__(self):
        name = "Ensure IAM roles have a maximum session duration set"
        id = "DC_IAM_009"
        supported_resources = ["aws_iam_role"]
        categories = [CheckCategories.IAM]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        max_session_duration = conf.get("max_session_duration", 3600)
        if isinstance(max_session_duration, list):
            max_session_duration = max_session_duration[0] if max_session_duration else 3600
        if not isinstance(max_session_duration, int) or max_session_duration > 3600:
            return CheckResult.FAILED
        return CheckResult.PASSED


class IAMPolicyNoFullAccess(BaseResourceCheck):
    """Ensure IAM policies do not grant full access to services."""

    FULL_ACCESS_PATTERNS = [
        '"Effect": "Allow", "Action": "*"',
        '"Effect":"Allow","Action":"*"',
        '"Action": "s3:*"',
        '"Action": "ec2:*"',
        '"Action": "iam:*"',
        '"Action": "rds:*"',
    ]

    def __init__(self):
        name = "Ensure IAM policies do not grant full access to services"
        id = "DC_IAM_010"
        supported_resources = [
            "aws_iam_policy",
            "aws_iam_role_policy",
            "aws_iam_group_policy",
            "aws_iam_user_policy",
        ]
        categories = [CheckCategories.IAM]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        policy = conf.get("policy", "")
        if isinstance(policy, list):
            policy = policy[0] if policy else ""
        if isinstance(policy, str):
            for pattern in self.FULL_ACCESS_PATTERNS:
                if pattern in policy:
                    return CheckResult.FAILED
        return CheckResult.PASSED
