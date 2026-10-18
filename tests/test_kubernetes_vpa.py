"""Tests for the Kubernetes VPA integration."""
import unittest
from datetime import datetime, timezone

from dcc.autoscaling.kubernetes_vpa import (
    ContainerScalingMode,
    ContainerUsageSample,
    CrossVersionObjectReference,
    PodResourcePolicy,
    PodUsageRecord,
    RecommendedContainerResources,
    RecommendationState,
    ResourceName,
    ResourcePolicy,
    RolloutConfig,
    RolloutPhase,
    RolloutState,
    RolloutStrategy,
    ScalingDecision,
    UpdateMode,
    UpdatePolicyConfig,
    UpdatePolicyEngine,
    VPACondition,
    VPAEngine,
    VPAObject,
    VPARecommendation,
    VPAReport,
    VPAMetricsSummary,
    VPARecommendationEngine,
)


def _make_resource_quantity(name, millicores=None, megabytes=None):
    """Helper to create a ResourceQuantity."""
    from dcc.autoscaling.kubernetes_vpa.models import ResourceQuantity

    return ResourceQuantity(
        name=name,
        quantity=f"{millicores or megabytes}",
        millicores=millicores,
        megabytes=megabytes,
    )


def _make_vpa_object(
    name="test-workload",
    namespace="default",
    update_mode=UpdateMode.AUTO,
    cpu_target=500,
    memory_target=512,
    cpu_lower=400,
    memory_lower=400,
    cpu_upper=600,
    memory_upper=600,
):
    """Helper to create a VPA object with recommendation."""
    target_ref = CrossVersionObjectReference(
        api_version="apps/v1",
        kind="Deployment",
        name=name,
    )

    cpu_qty = _make_resource_quantity("cpu", millicores=cpu_target)
    mem_qty = _make_resource_quantity("memory", megabytes=memory_target)
    cpu_lower_qty = _make_resource_quantity("cpu", millicores=cpu_lower)
    mem_lower_qty = _make_resource_quantity("memory", megabytes=memory_lower)
    cpu_upper_qty = _make_resource_quantity("cpu", millicores=cpu_upper)
    mem_upper_qty = _make_resource_quantity("memory", megabytes=memory_upper)

    container_rec = RecommendedContainerResources(
        container_name="app",
        target={"cpu": cpu_qty, "memory": mem_qty},
        lower_bound={"cpu": cpu_lower_qty, "memory": mem_lower_qty},
        upper_bound={"cpu": cpu_upper_qty, "memory": mem_upper_qty},
    )

    recommendation = VPARecommendation(
        container_recommendations=[container_rec],
        state=RecommendationState.PENDING,
        last_update_time=datetime.now(timezone.utc).isoformat(),
    )

    return VPAObject(
        name=f"vpa-{name}",
        namespace=namespace,
        target_ref=target_ref,
        recommendation=recommendation,
    )


class TestModels(unittest.TestCase):
    """Test VPA data models."""

    def test_vpa_object_creation(self):
        vpa = _make_vpa_object()
        self.assertEqual(vpa.target_ref.name, "test-workload")
        self.assertEqual(vpa.namespace, "default")
        self.assertIsNotNone(vpa.recommendation)

    def test_update_mode_enum(self):
        self.assertEqual(UpdateMode.OFF.value, "Off")
        self.assertEqual(UpdateMode.INITIAL.value, "Initial")
        self.assertEqual(UpdateMode.AUTO.value, "Auto")
        self.assertEqual(UpdateMode.RECREATE.value, "Recreate")

    def test_container_scaling_mode_enum(self):
        self.assertEqual(ContainerScalingMode.AUTO.value, "Auto")
        self.assertEqual(ContainerScalingMode.OFF.value, "Off")

    def test_recommendation_state_enum(self):
        self.assertEqual(RecommendationState.PENDING.value, "Pending")
        self.assertEqual(RecommendationState.ACCEPTED.value, "Accepted")
        self.assertEqual(RecommendationState.REJECTED.value, "Rejected")
        self.assertEqual(RecommendationState.FAILED.value, "Failed")

    def test_resource_policy_defaults(self):
        policy = ResourcePolicy(container_name="app")
        self.assertEqual(policy.mode, ContainerScalingMode.AUTO)
        self.assertIsNone(policy.min_allowed_cpu_millicores)
        self.assertIsNone(policy.max_allowed_cpu_millicores)

    def test_pod_resource_policy(self):
        policy = PodResourcePolicy(
            container_policies=[
                ResourcePolicy(container_name="app"),
                ResourcePolicy(container_name="sidecar"),
            ]
        )
        self.assertEqual(len(policy.container_policies), 2)

    def test_scaling_decision(self):
        decision = ScalingDecision(
            workload_name="test",
            namespace="default",
            container_name="app",
            current_cpu_millicores=250,
            current_memory_mb=256,
            recommended_cpu_millicores=500,
            recommended_memory_mb=512,
            cpu_change_percent=100.0,
            memory_change_percent=100.0,
            action="scale_up",
            reason="Test scale up",
            confidence=0.8,
        )
        self.assertEqual(decision.action, "scale_up")
        self.assertAlmostEqual(decision.confidence, 0.8)


class TestVPARecommendationEngine(unittest.TestCase):
    """Test VPA recommendation analysis."""

    def setUp(self):
        self.engine = VPARecommendationEngine()

    def test_analyze_scale_up(self):
        vpa = _make_vpa_object(cpu_target=500, memory_target=512)
        decisions = self.engine.analyze_recommendation(vpa, 250, 256)
        self.assertGreater(len(decisions), 0)
        self.assertEqual(decisions[0].action, "scale_up")

    def test_analyze_scale_down(self):
        vpa = _make_vpa_object(cpu_target=100, memory_target=128)
        decisions = self.engine.analyze_recommendation(vpa, 500, 512)
        self.assertGreater(len(decisions), 0)
        self.assertEqual(decisions[0].action, "scale_down")

    def test_analyze_no_change(self):
        vpa = _make_vpa_object(cpu_target=260, memory_target=260)
        decisions = self.engine.analyze_recommendation(vpa, 250, 256)
        # Should be no_change since difference is small
        if decisions:
            self.assertEqual(decisions[0].action, "no_change")

    def test_rejected_recommendation_returns_empty(self):
        vpa = _make_vpa_object()
        vpa.recommendation.state = RecommendationState.REJECTED
        decisions = self.engine.analyze_recommendation(vpa, 250, 256)
        self.assertEqual(len(decisions), 0)

    def test_no_recommendation_returns_empty(self):
        vpa = _make_vpa_object()
        vpa.recommendation = None
        decisions = self.engine.analyze_recommendation(vpa, 250, 256)
        self.assertEqual(len(decisions), 0)

    def test_confidence_filtering(self):
        engine = VPARecommendationEngine(min_confidence=0.9)
        vpa = _make_vpa_object(cpu_target=500, memory_target=512)
        decisions = engine.analyze_recommendation(vpa, 250, 256)
        # High confidence threshold may filter out decisions
        for d in decisions:
            self.assertGreaterEqual(d.confidence, 0.9)

    def test_percent_change_calculation(self):
        self.assertEqual(self.engine._percent_change(100, 150), 50.0)
        self.assertEqual(self.engine._percent_change(100, 50), -50.0)
        self.assertEqual(self.engine._percent_change(0, 100), 0.0)

    def test_determine_action_scale_up(self):
        action = self.engine._determine_action(50.0, 30.0)
        self.assertEqual(action, "scale_up")

    def test_determine_action_scale_down(self):
        action = self.engine._determine_action(-50.0, -30.0)
        self.assertEqual(action, "scale_down")

    def test_determine_action_no_change(self):
        action = self.engine._determine_action(5.0, 5.0)
        self.assertEqual(action, "no_change")

    def test_compute_metrics_summary(self):
        records = [
            PodUsageRecord(
                pod_name="pod-1",
                namespace="default",
                samples=[
                    ContainerUsageSample(
                        container_name="app",
                        cpu_usage_millicores=100.0,
                        memory_usage_mb=128.0,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    ),
                    ContainerUsageSample(
                        container_name="app",
                        cpu_usage_millicores=200.0,
                        memory_usage_mb=256.0,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    ),
                ],
            )
        ]
        summary = self.engine.compute_metrics_summary(
            records, "test-workload", "default"
        )
        self.assertEqual(summary.workload_name, "test-workload")
        self.assertEqual(summary.container_count, 1)
        self.assertEqual(summary.sample_count, 2)
        self.assertAlmostEqual(summary.avg_cpu_millicores, 150.0)
        self.assertAlmostEqual(summary.avg_memory_mb, 192.0)

    def test_filter_by_policy_off_mode(self):
        decisions = [
            ScalingDecision(
                workload_name="test",
                namespace="default",
                container_name="app",
                current_cpu_millicores=250,
                current_memory_mb=256,
                recommended_cpu_millicores=500,
                recommended_memory_mb=512,
                cpu_change_percent=100.0,
                memory_change_percent=100.0,
                action="scale_up",
                reason="Test",
                confidence=0.8,
            )
        ]
        policy = PodResourcePolicy(
            container_policies=[
                ResourcePolicy(
                    container_name="app",
                    mode=ContainerScalingMode.OFF,
                )
            ]
        )
        filtered = self.engine.filter_by_policy(decisions, policy)
        self.assertEqual(len(filtered), 0)

    def test_filter_by_policy_max_constraint(self):
        decisions = [
            ScalingDecision(
                workload_name="test",
                namespace="default",
                container_name="app",
                current_cpu_millicores=250,
                current_memory_mb=256,
                recommended_cpu_millicores=5000,
                recommended_memory_mb=5120,
                cpu_change_percent=1900.0,
                memory_change_percent=1900.0,
                action="scale_up",
                reason="Test",
                confidence=0.8,
            )
        ]
        policy = PodResourcePolicy(
            container_policies=[
                ResourcePolicy(
                    container_name="app",
                    mode=ContainerScalingMode.AUTO,
                    max_allowed_cpu_millicores=1000,
                    max_allowed_memory_mb=1024,
                )
            ]
        )
        filtered = self.engine.filter_by_policy(decisions, policy)
        self.assertEqual(len(filtered), 0)

    def test_filter_by_policy_passes(self):
        decisions = [
            ScalingDecision(
                workload_name="test",
                namespace="default",
                container_name="app",
                current_cpu_millicores=250,
                current_memory_mb=256,
                recommended_cpu_millicores=500,
                recommended_memory_mb=512,
                cpu_change_percent=100.0,
                memory_change_percent=100.0,
                action="scale_up",
                reason="Test",
                confidence=0.8,
            )
        ]
        policy = PodResourcePolicy(
            container_policies=[
                ResourcePolicy(
                    container_name="app",
                    mode=ContainerScalingMode.AUTO,
                    max_allowed_cpu_millicores=1000,
                    max_allowed_memory_mb=1024,
                )
            ]
        )
        filtered = self.engine.filter_by_policy(decisions, policy)
        self.assertEqual(len(filtered), 1)


class TestUpdatePolicyEngine(unittest.TestCase):
    """Test VPA update policy engine."""

    def setUp(self):
        self.config = UpdatePolicyConfig(
            update_mode=UpdateMode.AUTO,
            min_replicas=2,
        )
        self.engine = UpdatePolicyEngine(self.config)

    def test_should_apply_off_mode(self):
        config = UpdatePolicyConfig(update_mode=UpdateMode.OFF)
        engine = UpdatePolicyEngine(config)
        decision = ScalingDecision(
            workload_name="test",
            namespace="default",
            container_name="app",
            current_cpu_millicores=250,
            current_memory_mb=256,
            recommended_cpu_millicores=500,
            recommended_memory_mb=512,
            cpu_change_percent=100.0,
            memory_change_percent=100.0,
            action="scale_up",
            reason="Test",
            confidence=0.8,
        )
        self.assertFalse(engine.should_apply(decision))

    def test_should_apply_initial_mode_scale_up(self):
        config = UpdatePolicyConfig(update_mode=UpdateMode.INITIAL)
        engine = UpdatePolicyEngine(config)
        decision = ScalingDecision(
            workload_name="test",
            namespace="default",
            container_name="app",
            current_cpu_millicores=250,
            current_memory_mb=256,
            recommended_cpu_millicores=500,
            recommended_memory_mb=512,
            cpu_change_percent=100.0,
            memory_change_percent=100.0,
            action="scale_up",
            reason="Test",
            confidence=0.8,
        )
        self.assertTrue(engine.should_apply(decision))

    def test_should_apply_initial_mode_scale_down(self):
        config = UpdatePolicyConfig(update_mode=UpdateMode.INITIAL)
        engine = UpdatePolicyEngine(config)
        decision = ScalingDecision(
            workload_name="test",
            namespace="default",
            container_name="app",
            current_cpu_millicores=500,
            current_memory_mb=512,
            recommended_cpu_millicores=250,
            recommended_memory_mb=256,
            cpu_change_percent=-50.0,
            memory_change_percent=-50.0,
            action="scale_down",
            reason="Test",
            confidence=0.8,
        )
        self.assertFalse(engine.should_apply(decision))

    def test_should_apply_auto_mode_respects_min_replicas(self):
        decision = ScalingDecision(
            workload_name="test",
            namespace="default",
            container_name="app",
            current_cpu_millicores=250,
            current_memory_mb=256,
            recommended_cpu_millicores=500,
            recommended_memory_mb=512,
            cpu_change_percent=100.0,
            memory_change_percent=100.0,
            action="scale_up",
            reason="Test",
            confidence=0.8,
        )
        # Below min_replicas
        self.assertFalse(self.engine.should_apply(decision, current_replicas=1))
        # At min_replicas
        self.assertTrue(self.engine.should_apply(decision, current_replicas=2))

    def test_rollout_state_transitions(self):
        state = RolloutState(phase=RolloutPhase.PENDING, replicas_total=10)
        state = self.engine.advance_rollout(state)
        self.assertEqual(state.phase, RolloutPhase.CANARY)
        self.assertGreater(state.current_percentage, 0)

        state = self.engine.advance_rollout(state)
        self.assertEqual(state.phase, RolloutPhase.ANALYZING)

    def test_rollout_rollback(self):
        state = RolloutState(phase=RolloutPhase.CANARY, replicas_total=10)
        state = self.engine.rollback(state)
        self.assertEqual(state.phase, RolloutPhase.ROLLED_BACK)
        self.assertEqual(state.current_percentage, 0)

    def test_validate_policy_valid(self):
        vpa = _make_vpa_object()
        errors = self.engine.validate_policy(vpa)
        self.assertEqual(len(errors), 0)

    def test_validate_policy_negative_min_replicas(self):
        vpa = _make_vpa_object()
        vpa.update_policy.min_replicas = -1
        errors = self.engine.validate_policy(vpa)
        self.assertGreater(len(errors), 0)

    def test_validate_policy_min_exceeds_max(self):
        vpa = _make_vpa_object()
        vpa.resource_policy = PodResourcePolicy(
            container_policies=[
                ResourcePolicy(
                    container_name="app",
                    min_allowed_cpu_millicores=1000,
                    max_allowed_cpu_millicores=500,
                )
            ]
        )
        errors = self.engine.validate_policy(vpa)
        self.assertGreater(len(errors), 0)

    def test_get_rollout_strategy(self):
        config = UpdatePolicyConfig(
            update_mode=UpdateMode.AUTO,
            rollout_config=RolloutConfig(strategy=RolloutStrategy.CANARY),
        )
        engine = UpdatePolicyEngine(config)
        strategy = engine.get_rollout_strategy()
        self.assertEqual(strategy, RolloutStrategy.CANARY)


class TestVPAEngine(unittest.TestCase):
    """Test main VPA engine."""

    def setUp(self):
        config = UpdatePolicyConfig(
            update_mode=UpdateMode.AUTO,
            min_replicas=1,
        )
        self.engine = VPAEngine(update_policy_config=config)

    def test_analyze_workload(self):
        vpa = _make_vpa_object(cpu_target=500, memory_target=512)
        decisions = self.engine.analyze_workload(vpa, 250, 256)
        self.assertGreater(len(decisions), 0)

    def test_analyze_all(self):
        vpa_objects = [
            _make_vpa_object(name="workload-1", cpu_target=500, memory_target=512),
            _make_vpa_object(name="workload-2", cpu_target=100, memory_target=128),
        ]
        current_resources = {
            "workload-1": (250, 256),
            "workload-2": (500, 512),
        }
        report = self.engine.analyze_all(vpa_objects, current_resources)
        self.assertEqual(report.total_workloads, 2)
        self.assertGreater(report.total_recommendations, 0)

    def test_analyze_all_with_missing_resources(self):
        vpa_objects = [_make_vpa_object(name="workload-1")]
        current_resources = {}
        report = self.engine.analyze_all(vpa_objects, current_resources)
        self.assertEqual(report.total_workloads, 1)
        self.assertEqual(len(report.errors), 1)

    def test_compute_metrics(self):
        records = [
            PodUsageRecord(
                pod_name="pod-1",
                namespace="default",
                samples=[
                    ContainerUsageSample(
                        container_name="app",
                        cpu_usage_millicores=100.0,
                        memory_usage_mb=128.0,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    ),
                ],
            )
        ]
        summary = self.engine.compute_metrics(records, "test", "default")
        self.assertEqual(summary.workload_name, "test")
        self.assertEqual(summary.sample_count, 1)

    def test_create_and_advance_rollout(self):
        state = self.engine.create_rollout(total_replicas=10)
        self.assertEqual(state.phase, RolloutPhase.PENDING)
        self.assertEqual(state.replicas_total, 10)

        state = self.engine.advance_rollout(state)
        self.assertEqual(state.phase, RolloutPhase.CANARY)

    def test_rollback_rollout(self):
        state = self.engine.create_rollout(total_replicas=10)
        state = self.engine.advance_rollout(state)
        state = self.engine.rollback_rollout(state)
        self.assertEqual(state.phase, RolloutPhase.ROLLED_BACK)

    def test_validate_vpa(self):
        vpa = _make_vpa_object()
        errors = self.engine.validate_vpa(vpa)
        self.assertEqual(len(errors), 0)


class TestVPAReport(unittest.TestCase):
    """Test VPA report generation."""

    def test_report_counts(self):
        report = VPAReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_workloads=5,
            total_recommendations=10,
            scale_up_count=4,
            scale_down_count=3,
            no_change_count=3,
        )
        self.assertEqual(report.scale_up_count, 4)
        self.assertEqual(report.scale_down_count, 3)
        self.assertEqual(report.no_change_count, 3)


if __name__ == "__main__":
    unittest.main()
