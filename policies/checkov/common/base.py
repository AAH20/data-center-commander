"""
Checkov Custom Policies — Common Base Classes and Utilities
Shared functionality for all data center policy checks.
"""

from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck


class BaseDataCenterCheck(BaseResourceCheck):
    """Base class for all data center custom checks with common utilities."""

    def __init__(self, name, id, categories, supported_resources):
        super().__init__(
            name=name,
            id=id,
            categories=categories,
            supported_resources=supported_resources,
        )

    def _get_ingress_rules(self, conf):
        """Extract ingress rules from various resource configurations."""
        rules = []
        if "ingress" in conf:
            for ingress in conf["ingress"]:
                if isinstance(ingress, dict):
                    rules.append(ingress)
        return rules

    def _is_public_cidr(self, cidr):
        """Check if a CIDR block is publicly accessible."""
        if isinstance(cidr, str):
            return cidr in ["0.0.0.0/0", "::/0"]
        return False

    def _port_in_range(self, port, from_port, to_port):
        """Check if a port falls within a range."""
        try:
            port = int(port)
            from_port = int(from_port) if from_port else port
            to_port = int(to_port) if to_port else port
            return from_port <= port <= to_port
        except (ValueError, TypeError):
            return False

    def _has_required_tags(self, conf, required_tags):
        """Check if resource has all required tags."""
        tags = conf.get("tags", {})
        if isinstance(tags, list):
            tags = tags[0] if tags else {}
        if isinstance(tags, dict):
            for tag in required_tags:
                if tag not in tags:
                    return False
            return True
        return False

    def _get_nested_value(self, conf, *keys, default=None):
        """Safely get a nested value from a configuration dict."""
        current = conf
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key, default)
            elif isinstance(current, list) and len(current) > 0:
                current = current[0].get(key, default) if isinstance(current[0], dict) else default
            else:
                return default
        return current
