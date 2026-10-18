"""Tests for dcc.policy — policy-as-code engine."""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from dcc.policy import (
    DecisionEffect,
    Effect,
    Policy,
    PolicyAuthzBridge,
    PolicyBundle,
    PolicyDecision,
    PolicyDocument,
    PolicyEngine,
    PolicyEvaluationError,
    PolicySyntaxError,
    PolicyValidationError,
    PolicyValidator,
    RegoParser,
    Rule,
    RuleCondition,
    SentinelParser,
    create_default_policy_bundle,
    load_bundle_from_file,
)


# ---------------------------------------------------------------------------
# RuleCondition
# ---------------------------------------------------------------------------


class TestRuleCondition:
    def test_simple_comparison(self):
        cond = RuleCondition("input.action == 'read'")
        assert cond.evaluate({"action": "read"}) is True
        assert cond.evaluate({"action": "write"}) is False

    def test_boolean_and(self):
        cond = RuleCondition("input.action == 'write' and input.environment.mfa_verified")
        assert cond.evaluate({"action": "write", "environment": {"mfa_verified": True}}) is True
        assert cond.evaluate({"action": "write", "environment": {"mfa_verified": False}}) is False

    def test_boolean_or(self):
        cond = RuleCondition("input.action == 'read' or input.action == 'list'")
        assert cond.evaluate({"action": "read"}) is True
        assert cond.evaluate({"action": "list"}) is True
        assert cond.evaluate({"action": "write"}) is False

    def test_not(self):
        cond = RuleCondition("not input.environment.mfa_verified")
        assert cond.evaluate({"environment": {"mfa_verified": False}}) is True
        assert cond.evaluate({"environment": {"mfa_verified": True}}) is False

    def test_in_operator(self):
        cond = RuleCondition("input.action in ['write', 'delete', 'execute']")
        assert cond.evaluate({"action": "write"}) is True
        assert cond.evaluate({"action": "read"}) is False

    def test_nested_attribute(self):
        cond = RuleCondition("input.resource.criticality == 'critical'")
        assert cond.evaluate({"resource": {"criticality": "critical"}}) is True
        assert cond.evaluate({"resource": {"criticality": "normal"}}) is False

    def test_missing_key_returns_none(self):
        cond = RuleCondition("input.missing_key is None")
        assert cond.evaluate({}) is True

    def test_forbidden_dunder(self):
        with pytest.raises(PolicySyntaxError):
            RuleCondition("input.__class__")

    def test_forbidden_import(self):
        with pytest.raises(PolicySyntaxError):
            RuleCondition("import os")

    def test_forbidden_eval(self):
        with pytest.raises(PolicySyntaxError):
            RuleCondition("eval('1+1')")

    def test_forbidden_getattr(self):
        with pytest.raises(PolicySyntaxError):
            RuleCondition("getattr(input, 'key')")

    def test_repr(self):
        cond = RuleCondition("input.action == 'read'")
        assert "input.action == 'read'" in repr(cond)


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------


class TestRule:
    def test_basic_rule(self):
        rule = Rule(
            name="test-rule",
            effect=Effect.DENY,
            condition="input.action == 'write'",
        )
        assert rule.name == "test-rule"
        assert rule.effect == Effect.DENY
        assert rule.evaluate({"action": "write"}) is True
        assert rule.evaluate({"action": "read"}) is False

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            Rule(name="", effect=Effect.ALLOW, condition="true")

    def test_empty_condition_raises(self):
        with pytest.raises(ValueError):
            Rule(name="test", effect=Effect.ALLOW, condition="")

    def test_frozen(self):
        rule = Rule(name="test", effect=Effect.ALLOW, condition="true")
        with pytest.raises(AttributeError):
            rule.name = "other"


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


class TestPolicy:
    def test_basic_policy(self):
        policy = Policy(
            name="test-policy",
            rules=[
                Rule(name="allow-read", effect=Effect.ALLOW, condition="input.action == 'read'"),
                Rule(name="deny-write", effect=Effect.DENY, condition="input.action == 'write'"),
            ],
        )
        assert policy.name == "test-policy"
        assert len(policy.rules) == 2

    def test_evaluate_allow(self):
        policy = Policy(
            name="test",
            rules=[
                Rule(name="allow-read", effect=Effect.ALLOW, condition="input.action == 'read'"),
            ],
        )
        decision = policy.evaluate({"action": "read"})
        assert decision.effect == DecisionEffect.ALLOW
        assert decision.allowed is True
        assert "allow-read" in decision.matched_rules

    def test_evaluate_deny(self):
        policy = Policy(
            name="test",
            rules=[
                Rule(name="deny-write", effect=Effect.DENY, condition="input.action == 'write'"),
            ],
        )
        decision = policy.evaluate({"action": "write"})
        assert decision.effect == DecisionEffect.DENY
        assert decision.denied is True

    def test_evaluate_abstain(self):
        policy = Policy(
            name="test",
            rules=[
                Rule(name="allow-read", effect=Effect.ALLOW, condition="input.action == 'read'"),
            ],
        )
        decision = policy.evaluate({"action": "write"})
        assert decision.effect == DecisionEffect.ABSTAIN
        assert decision.abstained is True

    def test_deny_takes_precedence_over_allow(self):
        policy = Policy(
            name="test",
            rules=[
                Rule(name="allow-all", effect=Effect.ALLOW, condition="true"),
                Rule(name="deny-write", effect=Effect.DENY, condition="input.action == 'write'"),
            ],
        )
        decision = policy.evaluate({"action": "write"})
        assert decision.denied is True

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            Policy(name="")

    def test_to_dict(self):
        policy = Policy(
            name="test",
            description="Test policy",
            rules=[
                Rule(name="r1", effect=Effect.ALLOW, condition="true"),
            ],
        )
        data = policy.to_dict()
        assert data["name"] == "test"
        assert data["description"] == "Test policy"
        assert len(data["rules"]) == 1
        assert data["rules"][0]["name"] == "r1"

    def test_from_dict(self):
        data = {
            "name": "test",
            "description": "Test policy",
            "version": "1.0.0",
            "metadata": {"team": "security"},
            "rules": [
                {"name": "r1", "effect": "allow", "condition": "true", "description": ""},
            ],
        }
        policy = Policy.from_dict(data)
        assert policy.name == "test"
        assert policy.version == "1.0.0"
        assert policy.metadata["team"] == "security"
        assert len(policy.rules) == 1


# ---------------------------------------------------------------------------
# PolicyDecision
# ---------------------------------------------------------------------------


class TestPolicyDecision:
    def test_allowed_property(self):
        d = PolicyDecision(policy_name="test", effect=DecisionEffect.ALLOW)
        assert d.allowed is True
        assert d.denied is False
        assert d.abstained is False

    def test_denied_property(self):
        d = PolicyDecision(policy_name="test", effect=DecisionEffect.DENY)
        assert d.allowed is False
        assert d.denied is True
        assert d.abstained is False

    def test_abstained_property(self):
        d = PolicyDecision(policy_name="test", effect=DecisionEffect.ABSTAIN)
        assert d.allowed is False
        assert d.denied is False
        assert d.abstained is True

    def test_to_dict(self):
        d = PolicyDecision(
            policy_name="test",
            effect=DecisionEffect.ALLOW,
            matched_rules=("r1", "r2"),
            reason="test reason",
        )
        data = d.to_dict()
        assert data["policy_name"] == "test"
        assert data["effect"] == "allow"
        assert data["matched_rules"] == ["r1", "r2"]
        assert data["reason"] == "test reason"

    def test_frozen(self):
        d = PolicyDecision(policy_name="test", effect=DecisionEffect.ALLOW)
        with pytest.raises(AttributeError):
            d.policy_name = "other"


# ---------------------------------------------------------------------------
# PolicyBundle
# ---------------------------------------------------------------------------


class TestPolicyBundle:
    def test_basic_bundle(self):
        bundle = PolicyBundle(
            name="test-bundle",
            policies=[
                Policy(name="p1", rules=[Rule(name="r1", effect=Effect.ALLOW, condition="true")]),
            ],
        )
        assert bundle.name == "test-bundle"
        assert "p1" in bundle.policies

    def test_add_remove_policy(self):
        bundle = PolicyBundle(name="test")
        policy = Policy(name="p1", rules=[Rule(name="r1", effect=Effect.ALLOW, condition="true")])
        bundle.add_policy(policy)
        assert "p1" in bundle.policies
        bundle.remove_policy("p1")
        assert "p1" not in bundle.policies

    def test_evaluate_deny(self):
        bundle = PolicyBundle(
            name="test",
            policies=[
                Policy(name="p1", rules=[Rule(name="r1", effect=Effect.DENY, condition="true")]),
            ],
        )
        decision = bundle.evaluate({})
        assert decision.denied is True

    def test_evaluate_allow(self):
        bundle = PolicyBundle(
            name="test",
            policies=[
                Policy(name="p1", rules=[Rule(name="r1", effect=Effect.ALLOW, condition="true")]),
            ],
        )
        decision = bundle.evaluate({})
        assert decision.allowed is True

    def test_evaluate_abstain(self):
        bundle = PolicyBundle(
            name="test",
            policies=[
                Policy(name="p1", rules=[Rule(name="r1", effect=Effect.ALLOW, condition="false")]),
            ],
        )
        decision = bundle.evaluate({})
        assert decision.abstained is True

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            PolicyBundle(name="")

    def test_to_dict(self):
        bundle = PolicyBundle(
            name="test",
            description="Test bundle",
            policies=[
                Policy(name="p1", rules=[Rule(name="r1", effect=Effect.ALLOW, condition="true")]),
            ],
        )
        data = bundle.to_dict()
        assert data["name"] == "test"
        assert data["description"] == "Test bundle"
        assert len(data["policies"]) == 1


# ---------------------------------------------------------------------------
# PolicyEngine
# ---------------------------------------------------------------------------


class TestPolicyEngine:
    def test_basic_engine(self):
        engine = PolicyEngine()
        assert len(engine.bundles) == 0

    def test_add_remove_bundle(self):
        engine = PolicyEngine()
        bundle = PolicyBundle(name="test")
        engine.add_bundle(bundle)
        assert "test" in engine.bundles
        engine.remove_bundle("test")
        assert "test" not in engine.bundles

    def test_evaluate_default_deny(self):
        engine = PolicyEngine(default_deny=True)
        decision = engine.evaluate({})
        assert decision.denied is True
        assert "fail-closed" in decision.reason

    def test_evaluate_default_allow(self):
        engine = PolicyEngine(default_deny=False)
        decision = engine.evaluate({})
        assert decision.allowed is True
        assert "fail-open" in decision.reason

    def test_evaluate_with_matching_policy(self):
        engine = PolicyEngine(
            bundles=[
                PolicyBundle(
                    name="test",
                    policies=[
                        Policy(
                            name="p1",
                            rules=[Rule(name="r1", effect=Effect.ALLOW, condition="true")],
                        ),
                    ],
                ),
            ]
        )
        decision = engine.evaluate({})
        assert decision.allowed is True

    def test_evaluate_with_denying_policy(self):
        engine = PolicyEngine(
            bundles=[
                PolicyBundle(
                    name="test",
                    policies=[
                        Policy(
                            name="p1",
                            rules=[Rule(name="r1", effect=Effect.DENY, condition="true")],
                        ),
                    ],
                ),
            ]
        )
        decision = engine.evaluate({})
        assert decision.denied is True

    def test_tenant_scoping(self):
        engine = PolicyEngine(
            bundles=[
                PolicyBundle(
                    name="test",
                    policies=[
                        Policy(
                            name="p1",
                            rules=[Rule(name="r1", effect=Effect.ALLOW, condition="true")],
                            metadata={"tenant_id": "tenant-a"},
                        ),
                    ],
                ),
            ]
        )
        # Should skip the bundle for a different tenant
        decision = engine.evaluate({}, tenant_id="tenant-b")
        assert decision.denied is True  # default deny

    def test_to_dict(self):
        engine = PolicyEngine(
            bundles=[PolicyBundle(name="test")],
        )
        data = engine.to_dict()
        assert len(data["bundles"]) == 1
        assert data["default_deny"] is True


# ---------------------------------------------------------------------------
# RegoParser
# ---------------------------------------------------------------------------


class TestRegoParser:
    def test_parse_simple_policy(self):
        rego = """
        package dcc.security.authz

        allow if {
            input.action == "read"
        }
        """
        parser = RegoParser()
        policy = parser.parse(rego)
        assert policy.name == "dcc.security.authz"
        assert len(policy.rules) == 1
        assert policy.rules[0].effect == Effect.ALLOW

    def test_parse_deny_rule(self):
        rego = """
        package dcc.security.authz

        deny if {
            input.action == "write"
        }
        """
        parser = RegoParser()
        policy = parser.parse(rego)
        assert len(policy.rules) == 1
        assert policy.rules[0].effect == Effect.DENY

    def test_parse_multiple_rules(self):
        rego = """
        package dcc.security.authz

        allow if {
            input.action == "read"
        }

        deny if {
            input.action == "write"
        }
        """
        parser = RegoParser()
        policy = parser.parse(rego)
        assert len(policy.rules) == 2

    def test_parse_default_allow(self):
        rego = """
        package dcc.security.authz

        default allow := true
        """
        parser = RegoParser()
        policy = parser.parse(rego)
        assert len(policy.rules) == 1
        assert policy.rules[0].effect == Effect.ALLOW

    def test_parse_default_deny(self):
        rego = """
        package dcc.security.authz

        default allow := false
        """
        parser = RegoParser()
        policy = parser.parse(rego)
        assert len(policy.rules) == 1
        assert policy.rules[0].effect == Effect.DENY

    def test_parse_multiline_body(self):
        rego = """
        package dcc.security.authz

        allow if {
            input.action == "read"
            input.resource.type == "asset"
        }
        """
        parser = RegoParser()
        policy = parser.parse(rego)
        assert len(policy.rules) == 1
        # The multiline body should be joined with 'and'
        assert " and " in policy.rules[0].condition

    def test_parse_comments_ignored(self):
        rego = """
        package dcc.security.authz

        # This is a comment
        allow if {
            input.action == "read"  # inline comment
        }
        """
        parser = RegoParser()
        policy = parser.parse(rego)
        assert len(policy.rules) == 1

    def test_missing_package_raises(self):
        rego = """
        allow if {
            input.action == "read"
        }
        """
        parser = RegoParser()
        with pytest.raises(PolicySyntaxError):
            parser.parse(rego)

    def test_parse_file(self, tmp_path: Path):
        rego_file = tmp_path / "policy.rego"
        rego_file.write_text("""
        package dcc.security.authz

        allow if {
            input.action == "read"
        }
        """)
        parser = RegoParser()
        policy = parser.parse_file(rego_file)
        assert policy.name == "dcc.security.authz"

    def test_parse_file_not_found(self):
        parser = RegoParser()
        with pytest.raises(FileNotFoundError):
            parser.parse_file("/nonexistent/path.rego")


# ---------------------------------------------------------------------------
# SentinelParser
# ---------------------------------------------------------------------------


class TestSentinelParser:
    def test_parse_simple_policy(self):
        sentinel = """
        main = rule {
            true
        }
        """
        parser = SentinelParser()
        policy = parser.parse(sentinel)
        assert policy.name == "sentinel-policy"
        assert len(policy.rules) == 1

    def test_parse_with_condition(self):
        sentinel = """
        main = rule {
            input.action is not "write"
        }
        """
        parser = SentinelParser()
        policy = parser.parse(sentinel)
        assert len(policy.rules) == 1
        assert "!=" in policy.rules[0].condition

    def test_missing_main_rule_raises(self):
        sentinel = """
        import "tfplan"
        """
        parser = SentinelParser()
        with pytest.raises(PolicySyntaxError):
            parser.parse(sentinel)

    def test_parse_file(self, tmp_path: Path):
        sentinel_file = tmp_path / "policy.sentinel"
        sentinel_file.write_text("""
        main = rule {
            true
        }
        """)
        parser = SentinelParser()
        policy = parser.parse_file(sentinel_file)
        assert policy.name == "sentinel-policy"


# ---------------------------------------------------------------------------
# PolicyValidator
# ---------------------------------------------------------------------------


class TestPolicyValidator:
    def test_valid_policy(self):
        policy = Policy(
            name="test",
            rules=[Rule(name="r1", effect=Effect.ALLOW, condition="true")],
        )
        validator = PolicyValidator()
        errors = validator.validate(policy)
        assert errors == []

    def test_empty_name(self):
        with pytest.raises(ValueError):
            Policy(
                name="",
                rules=[Rule(name="r1", effect=Effect.ALLOW, condition="true")],
            )

    def test_no_rules(self):
        policy = Policy(name="test", rules=[])
        validator = PolicyValidator()
        errors = validator.validate(policy)
        assert any("at least one rule" in e for e in errors)

    def test_duplicate_rule_names(self):
        policy = Policy(
            name="test",
            rules=[
                Rule(name="r1", effect=Effect.ALLOW, condition="true"),
                Rule(name="r1", effect=Effect.DENY, condition="false"),
            ],
        )
        validator = PolicyValidator()
        errors = validator.validate(policy)
        assert any("duplicate" in e for e in errors)

    def test_invalid_condition(self):
        with pytest.raises(PolicySyntaxError):
            Rule(name="r1", effect=Effect.ALLOW, condition="import os")

    def test_validate_bundle(self):
        bundle = PolicyBundle(
            name="test",
            policies=[
                Policy(name="p1", rules=[Rule(name="r1", effect=Effect.ALLOW, condition="true")]),
            ],
        )
        validator = PolicyValidator()
        errors = validator.validate_bundle(bundle)
        assert errors == []

    def test_validate_engine(self):
        engine = PolicyEngine(
            bundles=[
                PolicyBundle(
                    name="test",
                    policies=[
                        Policy(
                            name="p1",
                            rules=[Rule(name="r1", effect=Effect.ALLOW, condition="true")],
                        ),
                    ],
                ),
            ]
        )
        validator = PolicyValidator()
        errors = validator.validate_engine(engine)
        assert errors == []


# ---------------------------------------------------------------------------
# Default policy bundle
# ---------------------------------------------------------------------------


class TestDefaultPolicyBundle:
    def test_create_default_bundle(self):
        bundle = create_default_policy_bundle()
        assert bundle.name == "default-security-policies"
        assert len(bundle.policies) >= 4

    def test_default_bundle_mfa_policy(self):
        bundle = create_default_policy_bundle()
        decision = bundle.evaluate({
            "resource": {"criticality": "critical"},
            "environment": {"mfa_verified": False},
        })
        assert decision.denied is True

    def test_default_bundle_mfa_verified(self):
        bundle = create_default_policy_bundle()
        decision = bundle.evaluate({
            "resource": {"criticality": "critical"},
            "environment": {"mfa_verified": True},
        })
        assert decision.allowed is True

    def test_default_bundle_business_hours(self):
        bundle = create_default_policy_bundle()
        decision = bundle.evaluate({
            "action": "write",
            "environment": {"business_hours": False},
        })
        assert decision.denied is True

    def test_default_bundle_tenant_isolation(self):
        bundle = create_default_policy_bundle()
        decision = bundle.evaluate({
            "resource": {"tenant_id": "other-tenant"},
            "tenant_id": "my-tenant",
        })
        assert decision.denied is True

    def test_default_bundle_viewer_read_only(self):
        bundle = create_default_policy_bundle()
        # Viewer can read
        decision = bundle.evaluate({
            "subject": {"roles": ["viewer"]},
            "action": "read",
        })
        assert decision.allowed is True

        # Viewer cannot write
        decision = bundle.evaluate({
            "subject": {"roles": ["viewer"]},
            "action": "write",
        })
        assert decision.denied is True


# ---------------------------------------------------------------------------
# PolicyDocument
# ---------------------------------------------------------------------------


class TestPolicyDocument:
    def test_from_json(self):
        json_str = json.dumps({
            "name": "test",
            "rules": [
                {"name": "r1", "effect": "allow", "condition": "true"},
            ],
        })
        policy = PolicyDocument.from_json(json_str)
        assert policy.name == "test"
        assert len(policy.rules) == 1

    def test_from_dict(self):
        data = {
            "name": "test",
            "rules": [
                {"name": "r1", "effect": "allow", "condition": "true"},
            ],
        }
        policy = PolicyDocument.from_dict(data)
        assert policy.name == "test"

    def test_from_file_json(self, tmp_path: Path):
        policy_file = tmp_path / "policy.json"
        policy_file.write_text(json.dumps({
            "name": "test",
            "rules": [
                {"name": "r1", "effect": "allow", "condition": "true"},
            ],
        }))
        policy = PolicyDocument.from_file(policy_file)
        assert policy.name == "test"

    def test_from_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            PolicyDocument.from_file("/nonexistent/policy.json")

    def test_invalid_json_raises(self):
        with pytest.raises(PolicySyntaxError):
            PolicyDocument.from_json("{invalid json}")


# ---------------------------------------------------------------------------
# PolicyAuthzBridge
# ---------------------------------------------------------------------------


class TestPolicyAuthzBridge:
    def test_can_allow(self):
        engine = PolicyEngine(
            bundles=[
                PolicyBundle(
                    name="test",
                    policies=[
                        Policy(
                            name="p1",
                            rules=[Rule(name="r1", effect=Effect.ALLOW, condition="true")],
                        ),
                    ],
                ),
            ]
        )
        bridge = PolicyAuthzBridge(engine)
        assert bridge.can(["viewer"], "read", "assets") is True

    def test_can_deny(self):
        engine = PolicyEngine(
            bundles=[
                PolicyBundle(
                    name="test",
                    policies=[
                        Policy(
                            name="p1",
                            rules=[Rule(name="r1", effect=Effect.DENY, condition="true")],
                        ),
                    ],
                ),
            ]
        )
        bridge = PolicyAuthzBridge(engine)
        assert bridge.can(["viewer"], "read", "assets") is False

    def test_authorize_raises_on_deny(self):
        engine = PolicyEngine(
            bundles=[
                PolicyBundle(
                    name="test",
                    policies=[
                        Policy(
                            name="p1",
                            rules=[Rule(name="r1", effect=Effect.DENY, condition="true")],
                        ),
                    ],
                ),
            ]
        )
        bridge = PolicyAuthzBridge(engine)
        with pytest.raises(PermissionError):
            bridge.authorize(["viewer"], "read", "assets")

    def test_authorize_passes_on_allow(self):
        engine = PolicyEngine(
            bundles=[
                PolicyBundle(
                    name="test",
                    policies=[
                        Policy(
                            name="p1",
                            rules=[Rule(name="r1", effect=Effect.ALLOW, condition="true")],
                        ),
                    ],
                ),
            ]
        )
        bridge = PolicyAuthzBridge(engine)
        # Should not raise
        bridge.authorize(["viewer"], "read", "assets")


# ---------------------------------------------------------------------------
# Bundle loading
# ---------------------------------------------------------------------------


class TestBundleLoading:
    def test_load_bundle_from_file(self, tmp_path: Path):
        bundle_file = tmp_path / "bundle.json"
        bundle_file.write_text(json.dumps({
            "name": "test-bundle",
            "description": "Test bundle",
            "policies": [
                {
                    "name": "p1",
                    "rules": [
                        {"name": "r1", "effect": "allow", "condition": "true"},
                    ],
                },
            ],
        }))
        bundle = load_bundle_from_file(bundle_file)
        assert bundle.name == "test-bundle"
        assert len(bundle.policies) == 1

    def test_load_bundle_from_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_bundle_from_file("/nonexistent/bundle.json")


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_rego_to_engine(self):
        rego = """
        package dcc.security.authz

        allow if {
            input.action == "read"
        }

        deny if {
            input.action == "write"
            not input.environment.mfa_verified
        }
        """
        parser = RegoParser()
        policy = parser.parse(rego)

        engine = PolicyEngine(bundles=[PolicyBundle(name="test", policies=[policy])])

        # Read should be allowed
        decision = engine.evaluate({"action": "read"})
        assert decision.allowed is True

        # Write without MFA should be denied
        decision = engine.evaluate({"action": "write", "environment": {"mfa_verified": False}})
        assert decision.denied is True

        # Write with MFA should be allowed (no matching deny, no matching allow -> default deny)
        decision = engine.evaluate({"action": "write", "environment": {"mfa_verified": True}})
        assert decision.denied is True  # default deny

    def test_sentinel_to_engine(self):
        sentinel = """
        main = rule {
            input.action is not "write"
        }
        """
        parser = SentinelParser()
        policy = parser.parse(sentinel)

        engine = PolicyEngine(bundles=[PolicyBundle(name="test", policies=[policy])])

        # Read should be allowed (main rule returns true)
        decision = engine.evaluate({"action": "read"})
        assert decision.allowed is True

        # Write should be denied (main rule returns false)
        decision = engine.evaluate({"action": "write"})
        assert decision.denied is True

    def test_full_pipeline(self):
        """Test the full pipeline: Rego -> Policy -> Bundle -> Engine -> Decision."""
        rego = """
        package dcc.security.policies

        import future.keywords.in

        default allow := false

        allow if {
            input.action in ["read", "list", "get"]
            input.subject.roles[_] == "viewer"
        }

        deny if {
            input.action == "delete"
            input.resource.criticality == "critical"
        }
        """
        parser = RegoParser()
        policy = parser.parse(rego)

        bundle = PolicyBundle(name="security", policies=[policy])
        engine = PolicyEngine(bundles=[bundle])

        # Viewer can read
        decision = engine.evaluate({
            "action": "read",
            "subject": {"roles": ["viewer"]},
        })
        assert decision.allowed is True

        # Non-viewer cannot read
        decision = engine.evaluate({
            "action": "read",
            "subject": {"roles": []},
        })
        assert decision.denied is True

        # Delete on critical resource is denied
        decision = engine.evaluate({
            "action": "delete",
            "resource": {"criticality": "critical"},
            "subject": {"roles": ["admin"]},
        })
        assert decision.denied is True
