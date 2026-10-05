"""Tests for auto-scaling engine: predictive and reactive scaling.

These tests verify that the auto-scaler can predict demand, scale proactively,
and handle burst traffic without cold starts.
"""

from __future__ import annotations

import unittest

from dcc.iac.autoscaler import (
    AutoScaler,
    ScalingPolicy,
    ScalingTrigger,
)


class TestScalingPolicy(unittest.TestCase):
    """Test scaling policy configuration."""

    def test_default_policy(self):
        """Default policy has sensible defaults."""
        policy = ScalingPolicy(
            min_instances=1,
            max_instances=10,
            target_cpu_percent=70.0,
            scale_up_threshold=80.0,
            scale_down_threshold=30.0,
            cooldown_seconds=60,
        )
        self.assertEqual(policy.min_instances, 1)
        self.assertEqual(policy.max_instances, 10)
        self.assertEqual(policy.target_cpu_percent, 70.0)

    def test_invalid_min_instances_rejected(self):
        """Negative min_instances must be rejected."""
        with self.assertRaises(ValueError):
            ScalingPolicy(
                min_instances=-1,
                max_instances=10,
                target_cpu_percent=70.0,
                scale_up_threshold=80.0,
                scale_down_threshold=30.0,
                cooldown_seconds=60,
            )

    def test_invalid_max_instances_rejected(self):
        """max_instances < min_instances must be rejected."""
        with self.assertRaises(ValueError):
            ScalingPolicy(
                min_instances=10,
                max_instances=1,
                target_cpu_percent=70.0,
                scale_up_threshold=80.0,
                scale_down_threshold=30.0,
                cooldown_seconds=60,
            )

    def test_invalid_thresholds_rejected(self):
        """scale_up_threshold must be > scale_down_threshold."""
        with self.assertRaises(ValueError):
            ScalingPolicy(
                min_instances=1,
                max_instances=10,
                target_cpu_percent=70.0,
                scale_up_threshold=30.0,
                scale_down_threshold=80.0,
                cooldown_seconds=60,
            )


class TestAutoScaler(unittest.TestCase):
    """Test auto-scaler decision making."""

    def test_scale_up_when_cpu_high(self):
        """Scale up when CPU exceeds threshold."""
        scaler = AutoScaler(
            policy=ScalingPolicy(
                min_instances=1,
                max_instances=10,
                target_cpu_percent=70.0,
                scale_up_threshold=80.0,
                scale_down_threshold=30.0,
                cooldown_seconds=60,
            )
        )
        decision = scaler.evaluate(
            current_instances=2,
            current_cpu_percent=85.0,
            current_memory_percent=60.0,
            request_rate=1000,
        )
        self.assertEqual(decision.action, ScalingTrigger.SCALE_UP)
        self.assertEqual(decision.target_instances, 3)

    def test_scale_down_when_cpu_low(self):
        """Scale down when CPU below threshold."""
        scaler = AutoScaler(
            policy=ScalingPolicy(
                min_instances=1,
                max_instances=10,
                target_cpu_percent=70.0,
                scale_up_threshold=80.0,
                scale_down_threshold=30.0,
                cooldown_seconds=60,
            )
        )
        decision = scaler.evaluate(
            current_instances=5,
            current_cpu_percent=20.0,
            current_memory_percent=30.0,
            request_rate=100,
        )
        self.assertEqual(decision.action, ScalingTrigger.SCALE_DOWN)
        self.assertEqual(decision.target_instances, 4)

    def test_no_action_when_cpu_normal(self):
        """No action when CPU is within normal range."""
        scaler = AutoScaler(
            policy=ScalingPolicy(
                min_instances=1,
                max_instances=10,
                target_cpu_percent=70.0,
                scale_up_threshold=80.0,
                scale_down_threshold=30.0,
                cooldown_seconds=60,
            )
        )
        decision = scaler.evaluate(
            current_instances=3,
            current_cpu_percent=65.0,
            current_memory_percent=50.0,
            request_rate=500,
        )
        self.assertEqual(decision.action, ScalingTrigger.NO_ACTION)
        self.assertEqual(decision.target_instances, 3)

    def test_respect_min_instances(self):
        """Never scale below min_instances."""
        scaler = AutoScaler(
            policy=ScalingPolicy(
                min_instances=2,
                max_instances=10,
                target_cpu_percent=70.0,
                scale_up_threshold=80.0,
                scale_down_threshold=30.0,
                cooldown_seconds=60,
            )
        )
        decision = scaler.evaluate(
            current_instances=2,
            current_cpu_percent=10.0,
            current_memory_percent=10.0,
            request_rate=10,
        )
        self.assertEqual(decision.target_instances, 2)

    def test_respect_max_instances(self):
        """Never scale above max_instances."""
        scaler = AutoScaler(
            policy=ScalingPolicy(
                min_instances=1,
                max_instances=5,
                target_cpu_percent=70.0,
                scale_up_threshold=80.0,
                scale_down_threshold=30.0,
                cooldown_seconds=60,
            )
        )
        decision = scaler.evaluate(
            current_instances=5,
            current_cpu_percent=95.0,
            current_memory_percent=90.0,
            request_rate=10000,
        )
        self.assertEqual(decision.target_instances, 5)

    def test_predictive_scaling(self):
        """Predictive scaling based on historical patterns."""
        scaler = AutoScaler(
            policy=ScalingPolicy(
                min_instances=1,
                max_instances=10,
                target_cpu_percent=70.0,
                scale_up_threshold=80.0,
                scale_down_threshold=30.0,
                cooldown_seconds=60,
            )
        )
        # Simulate historical data showing increasing load
        for i in range(10):
            scaler.record_metrics(
                timestamp=i * 60,
                cpu_percent=50.0 + i * 5,
                memory_percent=40.0 + i * 3,
                request_rate=100 + i * 100,
            )
        decision = scaler.evaluate(
            current_instances=2,
            current_cpu_percent=75.0,
            current_memory_percent=60.0,
            request_rate=800,
        )
        # Predictive scaling should trigger even though current CPU is below threshold
        self.assertEqual(decision.action, ScalingTrigger.SCALE_UP)

    def test_burst_handling(self):
        """Burst traffic triggers immediate scale up."""
        scaler = AutoScaler(
            policy=ScalingPolicy(
                min_instances=1,
                max_instances=10,
                target_cpu_percent=70.0,
                scale_up_threshold=80.0,
                scale_down_threshold=30.0,
                cooldown_seconds=60,
            )
        )
        decision = scaler.evaluate(
            current_instances=2,
            current_cpu_percent=75.0,
            current_memory_percent=60.0,
            request_rate=5000,  # Burst
        )
        self.assertEqual(decision.action, ScalingTrigger.SCALE_UP)

    def test_cooldown_respected(self):
        """Scaling decisions respect cooldown period."""
        scaler = AutoScaler(
            policy=ScalingPolicy(
                min_instances=1,
                max_instances=10,
                target_cpu_percent=70.0,
                scale_up_threshold=80.0,
                scale_down_threshold=30.0,
                cooldown_seconds=60,
            )
        )
        # First decision: scale up
        decision1 = scaler.evaluate(
            current_instances=2,
            current_cpu_percent=85.0,
            current_memory_percent=60.0,
            request_rate=1000,
        )
        self.assertEqual(decision1.action, ScalingTrigger.SCALE_UP)
        # Record the scaling action
        scaler.record_scaling_action(decision1)
        # Second decision during cooldown: no action
        decision2 = scaler.evaluate(
            current_instances=3,
            current_cpu_percent=90.0,
            current_memory_percent=70.0,
            request_rate=2000,
        )
        self.assertEqual(decision2.action, ScalingTrigger.COOLDOWN)

    def test_empty_metrics_history(self):
        """No predictive scaling without historical data."""
        scaler = AutoScaler(
            policy=ScalingPolicy(
                min_instances=1,
                max_instances=10,
                target_cpu_percent=70.0,
                scale_up_threshold=80.0,
                scale_down_threshold=30.0,
                cooldown_seconds=60,
            )
        )
        decision = scaler.evaluate(
            current_instances=2,
            current_cpu_percent=75.0,
            current_memory_percent=60.0,
            request_rate=800,
        )
        # Without historical data, should use reactive scaling only
        self.assertEqual(decision.action, ScalingTrigger.NO_ACTION)


if __name__ == "__main__":
    unittest.main()
