"""Tests for IaC engine: plan/apply with drift detection.

These tests verify that the engine can plan changes, apply them safely,
detect drift in real-time, and rollback on failure.
"""

from __future__ import annotations

import unittest

from dcc.iac.dsl import (
    ResourceType,
    define_resource,
    define_tenant,
)
from dcc.iac.engine import (
    EngineAction,
    PlanResult,
    PlanStep,
    apply_plan,
    detect_drift,
    generate_plan,
)


class TestPlanGeneration(unittest.TestCase):
    """Test plan generation from desired vs actual state."""

    def test_plan_no_changes_when_states_match(self):
        """No plan steps when desired and actual states match."""
        desired = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        actual = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        plan = generate_plan(desired, actual)
        self.assertEqual(plan.steps, [])
        self.assertFalse(plan.has_changes)

    def test_plan_detects_added_resource(self):
        """Plan detects resource that needs to be added."""
        desired = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
                define_resource(
                    name="web-2",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        actual = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        plan = generate_plan(desired, actual)
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].action, EngineAction.CREATE)
        self.assertEqual(plan.steps[0].resource_name, "web-2")

    def test_plan_detects_removed_resource(self):
        """Plan detects resource that needs to be removed."""
        desired = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        actual = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
                define_resource(
                    name="web-2",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        plan = generate_plan(desired, actual)
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].action, EngineAction.DESTROY)
        self.assertEqual(plan.steps[0].resource_name, "web-2")

    def test_plan_detects_modified_resource(self):
        """Plan detects resource that needs to be updated."""
        desired = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=8,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        actual = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        plan = generate_plan(desired, actual)
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].action, EngineAction.UPDATE)
        self.assertEqual(plan.steps[0].resource_name, "web-1")

    def test_plan_ordering(self):
        """Plan steps are ordered: destroy, update, create."""
        desired = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=8,
                    memory_gb=16,
                    region="us-east-1",
                ),
                define_resource(
                    name="web-3",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        actual = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
                define_resource(
                    name="web-2",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        plan = generate_plan(desired, actual)
        self.assertEqual(len(plan.steps), 3)
        # Destroy first, then update, then create
        self.assertEqual(plan.steps[0].action, EngineAction.DESTROY)
        self.assertEqual(plan.steps[1].action, EngineAction.UPDATE)
        self.assertEqual(plan.steps[2].action, EngineAction.CREATE)


class TestDriftDetection(unittest.TestCase):
    """Test real-time drift detection."""

    def test_no_drift_when_states_match(self):
        """No drift when desired and actual states match."""
        desired = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        actual = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        report = detect_drift(desired, actual)
        self.assertFalse(report.has_drift)
        self.assertEqual(report.drifted_resources, [])

    def test_drift_detected_when_states_differ(self):
        """Drift detected when desired and actual states differ."""
        desired = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=8,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        actual = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        report = detect_drift(desired, actual)
        self.assertTrue(report.has_drift)
        self.assertIn("web-1", report.drifted_resources)

    def test_drift_report_includes_details(self):
        """Drift report includes detailed change information."""
        desired = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=8,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        actual = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        report = detect_drift(desired, actual)
        self.assertIn("web-1", report.details)
        self.assertIn("cpu_cores", report.details["web-1"]["changes"])


class TestApplyPlan(unittest.TestCase):
    """Test plan application with rollback on failure."""

    def test_apply_empty_plan(self):
        """Applying empty plan is a no-op."""
        plan = PlanResult(steps=[], has_changes=False)
        result = apply_plan(plan)
        self.assertTrue(result.success)
        self.assertEqual(result.applied_steps, 0)

    def test_apply_create_step(self):
        """Create step adds resource to actual state."""
        desired = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        actual = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[],
        )
        plan = generate_plan(desired, actual)

        def mutator(step: PlanStep, rollback: bool = False) -> None:
            if step.action == EngineAction.CREATE and step.resource:
                if rollback:
                    actual.resources = [r for r in actual.resources if r.name != step.resource_name]
                else:
                    actual.resources.append(step.resource)

        result = apply_plan(plan, mutator=mutator)
        self.assertTrue(result.success)
        self.assertEqual(result.applied_steps, 1)
        self.assertEqual(len(actual.resources), 1)

    def test_apply_with_rollback_on_failure(self):
        """Failed step triggers rollback of previous steps."""
        desired = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[
                define_resource(
                    name="web-1",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
                define_resource(
                    name="web-2",
                    resource_type=ResourceType.COMPUTE,
                    cpu_cores=4,
                    memory_gb=16,
                    region="us-east-1",
                ),
            ],
        )
        actual = define_tenant(
            name="test-tenant",
            region="us-east-1",
            resources=[],
        )
        plan = generate_plan(desired, actual)

        def mutator(step: PlanStep, rollback: bool = False) -> None:
            if step.action == EngineAction.CREATE and step.resource:
                if rollback:
                    actual.resources = [r for r in actual.resources if r.name != step.resource_name]
                else:
                    actual.resources.append(step.resource)

        # Simulate failure on second step (index 1 = second CREATE)
        result = apply_plan(plan, fail_on_step=1, mutator=mutator)
        self.assertFalse(result.success)
        self.assertEqual(result.applied_steps, 1)
        self.assertTrue(result.rolled_back)
        # After rollback, all completed steps are undone (back to original state)
        self.assertEqual(len(actual.resources), 0)


if __name__ == "__main__":
    unittest.main()
