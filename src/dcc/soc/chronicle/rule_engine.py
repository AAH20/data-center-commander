"""Rule engine for Google Chronicle SOC integration.

Provides a detection engine that evaluates YARA-L rules against
security events and produces detections. Supports rule management,
versioning, and batch evaluation.

Pure-Python implementation with no external dependencies.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

from .models import (
    Detection,
    DetectionStatus,
    EventSeverity,
    RuleSeverity,
    RuleStatus,
    SecurityEvent,
    YaraRule,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RuleEngineError(Exception):
    """Base exception for rule engine failures."""


class RuleNotFoundError(RuleEngineError):
    """Raised when a rule is not found."""


class RuleValidationError(RuleEngineError):
    """Raised when a rule fails validation."""


class RuleEvaluationError(RuleEngineError):
    """Raised when rule evaluation fails."""


# ---------------------------------------------------------------------------
# Rule match
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuleMatch:
    """A single rule match result.

    Attributes
    ----------
    rule:
        The rule that matched.
    event:
        The event that triggered the match.
    matched_fields:
        Fields that contributed to the match.
    confidence:
        Confidence score (0.0 to 1.0).
    """

    rule: YaraRule
    event: SecurityEvent
    matched_fields: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

    def to_detection(self) -> Detection:
        """Convert this match to a Detection."""
        return Detection(
            rule_id=self.rule.rule_id,
            rule_name=self.rule.name,
            status=DetectionStatus.NEW,
            severity=self.rule.severity,
            event=self.event,
            description=f"Rule '{self.rule.name}' matched: {self.rule.description}",
            metadata={
                "matched_fields": self.matched_fields,
                "confidence": self.confidence,
                "rule_version": self.rule.version,
            },
        )


# ---------------------------------------------------------------------------
# Rule validator
# ---------------------------------------------------------------------------


class RuleValidator:
    """Validates YARA-L rules before deployment."""

    def validate(self, rule: YaraRule) -> list[str]:
        """Validate a YARA-L rule and return a list of issues."""
        issues: list[str] = []

        if not rule.name:
            issues.append("Rule name is required")

        if not rule.yara_l:
            issues.append("YARA-L source is required")

        if rule.severity not in RuleSeverity:
            issues.append(f"Invalid severity: {rule.severity}")

        # Basic YARA-L syntax checks
        yara_l = rule.yara_l.strip()
        if yara_l:
            if "rule " not in yara_l and "meta:" not in yara_l:
                issues.append("YARA-L rule must contain 'rule' keyword and 'meta' section")

            # Check for balanced braces
            if yara_l.count("{") != yara_l.count("}"):
                issues.append("Unbalanced braces in YARA-L rule")

            # Check for balanced parentheses
            if yara_l.count("(") != yara_l.count(")"):
                issues.append("Unbalanced parentheses in YARA-L rule")

        return issues

    def is_valid(self, rule: YaraRule) -> bool:
        """Check if a rule is valid."""
        return len(self.validate(rule)) == 0


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------


class RuleEngine:
    """Engine for evaluating YARA-L rules against security events.

    Supports both YARA-L rules (stored as source) and Python-based
    detection functions for testing and custom logic.
    """

    def __init__(self) -> None:
        self._rules: dict[str, YaraRule] = {}
        self._detection_functions: dict[str, Callable[[SecurityEvent], bool]] = {}
        self._validator = RuleValidator()

    @property
    def rules(self) -> list[YaraRule]:
        """Get all registered rules."""
        return list(self._rules.values())

    @property
    def enabled_rules(self) -> list[YaraRule]:
        """Get all enabled rules."""
        return [r for r in self._rules.values() if r.status == RuleStatus.ENABLED]

    def register(self, rule: YaraRule) -> None:
        """Register a YARA-L rule."""
        issues = self._validator.validate(rule)
        if issues:
            raise RuleValidationError(f"Rule validation failed: {'; '.join(issues)}")
        self._rules[rule.rule_id] = rule

    def unregister(self, rule_id: str) -> bool:
        """Unregister a rule."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def get_rule(self, rule_id: str) -> YaraRule:
        """Get a rule by ID."""
        if rule_id not in self._rules:
            raise RuleNotFoundError(f"Rule not found: {rule_id}")
        return self._rules[rule_id]

    def enable_rule(self, rule_id: str) -> None:
        """Enable a rule."""
        rule = self.get_rule(rule_id)
        rule.enable()

    def disable_rule(self, rule_id: str) -> None:
        """Disable a rule."""
        rule = self.get_rule(rule_id)
        rule.disable()

    def register_detection_function(
        self,
        rule_id: str,
        func: Callable[[SecurityEvent], bool],
    ) -> None:
        """Register a Python detection function for a rule."""
        self._detection_functions[rule_id] = func

    def evaluate(self, event: SecurityEvent) -> list[RuleMatch]:
        """Evaluate all enabled rules against a security event."""
        matches: list[RuleMatch] = []

        for rule in self.enabled_rules:
            # Check if there's a Python detection function
            if rule.rule_id in self._detection_functions:
                func = self._detection_functions[rule.rule_id]
                try:
                    if func(event):
                        matches.append(RuleMatch(
                            rule=rule,
                            event=event,
                            matched_fields={"detection_function": True},
                        ))
                except Exception:
                    continue
            else:
                # Evaluate YARA-L rule using pattern matching
                match = self._evaluate_yara_l(rule, event)
                if match:
                    matches.append(match)

        return matches

    def evaluate_batch(self, events: Sequence[SecurityEvent]) -> list[RuleMatch]:
        """Evaluate all enabled rules against a batch of events."""
        matches: list[RuleMatch] = []
        for event in events:
            matches.extend(self.evaluate(event))
        return matches

    def _evaluate_yara_l(self, rule: YaraRule, event: SecurityEvent) -> RuleMatch | None:
        """Evaluate a YARA-L rule against an event using pattern matching.

        This is a simplified evaluation that extracts patterns from the
        YARA-L source and checks them against the event data.
        """
        yara_l = rule.yara_l

        # Extract event field conditions from YARA-L
        # Look for patterns like: $event.field == "value"
        field_patterns = re.findall(
            r'\$(\w+)\.(\w+)\s*==\s*"([^"]*)"',
            yara_l,
        )

        if not field_patterns:
            # No specific field conditions, check for general patterns
            return self._evaluate_general_patterns(rule, event)

        matched_fields: dict[str, Any] = {}
        all_matched = True

        for var_name, field_name, expected_value in field_patterns:
            actual_value = self._get_event_field(event, field_name)
            if actual_value is None or str(actual_value) != expected_value:
                all_matched = False
                break
            matched_fields[field_name] = actual_value

        if all_matched:
            return RuleMatch(
                rule=rule,
                event=event,
                matched_fields=matched_fields,
            )

        return None

    def _evaluate_general_patterns(self, rule: YaraRule, event: SecurityEvent) -> RuleMatch | None:
        """Evaluate general patterns in a YARA-L rule."""
        yara_l = rule.yara_l.lower()
        event_str = str(event.to_dict()).lower()

        # Check for keyword patterns in the YARA-L rule
        keywords = re.findall(r'"([a-z_]+)"', yara_l)
        matched = [kw for kw in keywords if kw in event_str]

        if matched:
            return RuleMatch(
                rule=rule,
                event=event,
                matched_fields={"keywords": matched},
                confidence=min(1.0, len(matched) / max(len(keywords), 1)),
            )

        return None

    def _get_event_field(self, event: SecurityEvent, field_name: str) -> Any:
        """Get a field value from a security event."""
        # Check metadata first
        if field_name in event.metadata:
            return event.metadata[field_name]
        # Check raw_event
        if field_name in event.raw_event:
            return event.raw_event[field_name]
        # Check top-level attributes
        return getattr(event, field_name, None)

    def create_detection(self, match: RuleMatch) -> Detection:
        """Create a detection from a rule match."""
        return match.to_detection()

    def evaluate_and_create(self, event: SecurityEvent) -> list[Detection]:
        """Evaluate rules and create detections for all matches."""
        matches = self.evaluate(event)
        return [self.create_detection(m) for m in matches]

    def evaluate_batch_and_create(self, events: Sequence[SecurityEvent]) -> list[Detection]:
        """Evaluate rules on a batch and create detections."""
        matches = self.evaluate_batch(events)
        return [self.create_detection(m) for m in matches]


# ---------------------------------------------------------------------------
# Rule manager
# ---------------------------------------------------------------------------


class RuleManager:
    """Manages YARA-L rules: CRUD, versioning, and deployment."""

    def __init__(self) -> None:
        self._rules: dict[str, YaraRule] = {}
        self._validator = RuleValidator()
        self._engine = RuleEngine()

    @property
    def rules(self) -> list[YaraRule]:
        """Get all managed rules."""
        return list(self._rules.values())

    def create_rule(
        self,
        name: str,
        description: str = "",
        yara_l: str = "",
        severity: RuleSeverity = RuleSeverity.MEDIUM,
        tags: list[str] | None = None,
    ) -> YaraRule:
        """Create a new YARA-L rule."""
        rule = YaraRule(
            name=name,
            description=description,
            yara_l=yara_l,
            severity=severity,
            status=RuleStatus.DRAFT,
            tags=tags or [],
        )
        issues = self._validator.validate(rule)
        if issues:
            raise RuleValidationError(f"Rule validation failed: {'; '.join(issues)}")
        self._rules[rule.rule_id] = rule
        return rule

    def get_rule(self, rule_id: str) -> YaraRule:
        """Get a rule by ID."""
        if rule_id not in self._rules:
            raise RuleNotFoundError(f"Rule not found: {rule_id}")
        return self._rules[rule_id]

    def update_rule(self, rule_id: str, **kwargs: Any) -> YaraRule:
        """Update a rule."""
        rule = self.get_rule(rule_id)
        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        rule.updated_at = datetime.now(timezone.utc)
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def deploy_rule(self, rule_id: str) -> None:
        """Deploy a rule to the engine."""
        rule = self.get_rule(rule_id)
        rule.enable()
        self._engine.register(rule)

    def undeploy_rule(self, rule_id: str) -> None:
        """Undeploy a rule from the engine."""
        self._engine.unregister(rule_id)

    def enable_rule(self, rule_id: str) -> None:
        """Enable a rule."""
        rule = self.get_rule(rule_id)
        rule.enable()

    def disable_rule(self, rule_id: str) -> None:
        """Disable a rule."""
        rule = self.get_rule(rule_id)
        rule.disable()

    def list_rules(
        self,
        status: RuleStatus | None = None,
        severity: RuleSeverity | None = None,
        tag: str | None = None,
    ) -> list[YaraRule]:
        """List rules with optional filtering."""
        rules = list(self._rules.values())
        if status:
            rules = [r for r in rules if r.status == status]
        if severity:
            rules = [r for r in rules if r.severity == severity]
        if tag:
            rules = [r for r in rules if tag in r.tags]
        return rules

    def get_engine(self) -> RuleEngine:
        """Get the rule engine with all deployed rules."""
        return self._engine


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def create_rule_engine() -> RuleEngine:
    """Create a new rule engine."""
    return RuleEngine()


def create_rule_manager() -> RuleManager:
    """Create a new rule manager."""
    return RuleManager()


def evaluate_event(event: SecurityEvent, rules: Sequence[YaraRule]) -> list[Detection]:
    """Evaluate an event against a set of rules."""
    engine = RuleEngine()
    for rule in rules:
        if rule.status == RuleStatus.ENABLED:
            engine.register(rule)
    return engine.evaluate_and_create(event)
