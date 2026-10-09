"""
Auto Scaling Tests
Validates HorizontalPodAutoscaler (HPA) and PodDisruptionBudget (PDB) configuration:
- HPA presence and configuration
- Scaling thresholds and behavior
- PDB for availability during disruptions
- Resource-based scaling metrics
- Scaling limits and bounds
"""

import pytest
from typing import Dict, List, Any


class TestHPAPresence:
    """HPA existence and coverage checks."""

    def test_hpas_exist(self, hpas):
        """At least one HPA should be defined."""
        assert len(hpas) >= 1, "No HorizontalPodAutoscalers found"

    def test_all_deployments_have_hpa(self, deployments, hpas):
        """Every scalable Deployment should have an HPA."""
        hpa_targets = set()
        for hpa in hpas:
            target = hpa.get("spec", {}).get("scaleTargetRef", {})
            if target.get("kind") == "Deployment":
                hpa_targets.add(target.get("name"))
        deployment_names = {d.get("metadata", {}).get("name") for d in deployments}
        missing = deployment_names - hpa_targets
        assert not missing, f"Deployments without HPA: {missing}"

    def test_hpas_in_correct_namespace(self, hpas, namespace):
        """HPAs should be in the data-center-commander namespace."""
        ns_name = namespace.get("metadata", {}).get("name", "data-center-commander") if namespace else "data-center-commander"
        violations = []
        for hpa in hpas:
            hpa_ns = hpa.get("metadata", {}).get("namespace")
            if hpa_ns and hpa_ns != ns_name:
                violations.append(
                    f"HPA/{hpa['metadata']['name']} in wrong namespace: {hpa_ns}"
                )
        assert not violations, f"HPAs in wrong namespace: {violations}"

    def test_hpas_have_labels(self, hpas):
        """HPAs should have labels."""
        violations = []
        for hpa in hpas:
            labels = hpa.get("metadata", {}).get("labels", {})
            if not labels:
                violations.append(
                    f"HPA/{hpa['metadata']['name']} has no labels"
                )
        assert not violations, f"Unlabeled HPAs found: {violations}"


class TestHPAConfiguration:
    """HPA configuration and threshold checks."""

    def test_hpa_min_replicas_at_least_1(self, hpas):
        """HPA minReplicas should be at least 1."""
        violations = []
        for hpa in hpas:
            min_replicas = hpa.get("spec", {}).get("minReplicas", 1)
            if min_replicas < 1:
                violations.append(
                    f"HPA/{hpa['metadata']['name']} has minReplicas < 1: {min_replicas}"
                )
        assert not violations, f"HPAs with minReplicas < 1: {violations}"

    def test_hpa_max_replicas_greater_than_min(self, hpas):
        """HPA maxReplicas should be greater than minReplicas."""
        violations = []
        for hpa in hpas:
            min_replicas = hpa.get("spec", {}).get("minReplicas", 1)
            max_replicas = hpa.get("spec", {}).get("maxReplicas", 1)
            if max_replicas <= min_replicas:
                violations.append(
                    f"HPA/{hpa['metadata']['name']} maxReplicas ({max_replicas}) <= minReplicas ({min_replicas})"
                )
        assert not violations, f"HPAs with invalid replica bounds: {violations}"

    def test_hpa_max_replicas_reasonable(self, hpas):
        """HPA maxReplicas should be reasonable (not excessively high)."""
        violations = []
        for hpa in hpas:
            max_replicas = hpa.get("spec", {}).get("maxReplicas", 1)
            if max_replicas > 100:
                violations.append(
                    f"HPA/{hpa['metadata']['name']} has excessive maxReplicas: {max_replicas}"
                )
        assert not violations, f"HPAs with excessive maxReplicas: {violations}"

    def test_hpa_has_cpu_metric(self, hpas):
        """HPAs should have CPU utilization metric."""
        violations = []
        for hpa in hpas:
            metrics = hpa.get("spec", {}).get("metrics", [])
            has_cpu = any(
                m.get("type") == "Resource" and m.get("resource", {}).get("name") == "cpu"
                for m in metrics
            )
            if not has_cpu:
                violations.append(
                    f"HPA/{hpa['metadata']['name']} missing CPU metric"
                )
        assert not violations, f"HPAs missing CPU metric: {violations}"

    def test_hpa_has_memory_metric(self, hpas):
        """HPAs should have memory utilization metric."""
        violations = []
        for hpa in hpas:
            metrics = hpa.get("spec", {}).get("metrics", [])
            has_memory = any(
                m.get("type") == "Resource" and m.get("resource", {}).get("name") == "memory"
                for m in metrics
            )
            if not has_memory:
                violations.append(
                    f"HPA/{hpa['metadata']['name']} missing memory metric"
                )
        assert not violations, f"HPAs missing memory metric: {violations}"

    def test_hpa_cpu_target_reasonable(self, hpas):
        """HPA CPU target utilization should be reasonable (50-90%)."""
        violations = []
        for hpa in hpas:
            metrics = hpa.get("spec", {}).get("metrics", [])
            for m in metrics:
                if m.get("type") == "Resource" and m.get("resource", {}).get("name") == "cpu":
                    target = m.get("resource", {}).get("target", {})
                    avg_util = target.get("averageUtilization")
                    if avg_util is not None and (avg_util < 50 or avg_util > 90):
                        violations.append(
                            f"HPA/{hpa['metadata']['name']} CPU target {avg_util}% outside 50-90% range"
                        )
        assert not violations, f"HPAs with unreasonable CPU targets: {violations}"

    def test_hpa_memory_target_reasonable(self, hpas):
        """HPA memory target utilization should be reasonable (50-90%)."""
        violations = []
        for hpa in hpas:
            metrics = hpa.get("spec", {}).get("metrics", [])
            for m in metrics:
                if m.get("type") == "Resource" and m.get("resource", {}).get("name") == "memory":
                    target = m.get("resource", {}).get("target", {})
                    avg_util = target.get("averageUtilization")
                    if avg_util is not None and (avg_util < 50 or avg_util > 90):
                        violations.append(
                            f"HPA/{hpa['metadata']['name']} memory target {avg_util}% outside 50-90% range"
                        )
        assert not violations, f"HPAs with unreasonable memory targets: {violations}"

    def test_hpa_uses_autoscaling_v2(self, hpas):
        """HPAs should use autoscaling/v2 API version."""
        violations = []
        for hpa in hpas:
            api_version = hpa.get("apiVersion", "")
            if "autoscaling/v2" not in api_version:
                violations.append(
                    f"HPA/{hpa['metadata']['name']} uses {api_version}, expected autoscaling/v2"
                )
        assert not violations, f"HPAs with wrong API version: {violations}"


class TestHPABehavior:
    """HPA scaling behavior checks."""

    def test_hpa_has_scale_down_behavior(self, hpas):
        """HPAs should have scale-down behavior configured."""
        violations = []
        for hpa in hpas:
            behavior = hpa.get("spec", {}).get("behavior", {})
            scale_down = behavior.get("scaleDown", {})
            if not scale_down:
                violations.append(
                    f"HPA/{hpa['metadata']['name']} missing scaleDown behavior"
                )
        assert not violations, f"HPAs missing scaleDown behavior: {violations}"

    def test_hpa_has_scale_up_behavior(self, hpas):
        """HPAs should have scale-up behavior configured."""
        violations = []
        for hpa in hpas:
            behavior = hpa.get("spec", {}).get("behavior", {})
            scale_up = behavior.get("scaleUp", {})
            if not scale_up:
                violations.append(
                    f"HPA/{hpa['metadata']['name']} missing scaleUp behavior"
                )
        assert not violations, f"HPAs missing scaleUp behavior: {violations}"

    def test_hpa_scale_down_stabilization_window(self, hpas):
        """Scale-down should have a stabilization window to prevent flapping."""
        violations = []
        for hpa in hpas:
            behavior = hpa.get("spec", {}).get("behavior", {})
            scale_down = behavior.get("scaleDown", {})
            stabilization = scale_down.get("stabilizationWindowSeconds", 0)
            if stabilization < 60:
                violations.append(
                    f"HPA/{hpa['metadata']['name']} scale-down stabilization window too short: {stabilization}s"
                )
        assert not violations, f"HPAs with short scale-down stabilization: {violations}"

    def test_hpa_scale_down_has_policies(self, hpas):
        """Scale-down should have explicit policies."""
        violations = []
        for hpa in hpas:
            behavior = hpa.get("spec", {}).get("behavior", {})
            scale_down = behavior.get("scaleDown", {})
            policies = scale_down.get("policies", [])
            if not policies:
                violations.append(
                    f"HPA/{hpa['metadata']['name']} scaleDown has no policies"
                )
        assert not violations, f"HPAs with no scale-down policies: {violations}"

    def test_hpa_scale_up_has_policies(self, hpas):
        """Scale-up should have explicit policies."""
        violations = []
        for hpa in hpas:
            behavior = hpa.get("spec", {}).get("behavior", {})
            scale_up = behavior.get("scaleUp", {})
            policies = scale_up.get("policies", [])
            if not policies:
                violations.append(
                    f"HPA/{hpa['metadata']['name']} scaleUp has no policies"
                )
        assert not violations, f"HPAs with no scale-up policies: {violations}"

    def test_hpa_scale_down_policy_type_percent(self, hpas):
        """Scale-down policies should use Percent type for gradual scaling."""
        violations = []
        for hpa in hpas:
            behavior = hpa.get("spec", {}).get("behavior", {})
            scale_down = behavior.get("scaleDown", {})
            policies = scale_down.get("policies", [])
            has_percent = any(p.get("type") == "Percent" for p in policies)
            if not has_percent:
                violations.append(
                    f"HPA/{hpa['metadata']['name']} scaleDown missing Percent policy"
                )
        assert not violations, f"HPAs missing Percent scale-down policy: {violations}"

    def test_hpa_scale_up_policy_type_percent(self, hpas):
        """Scale-up policies should use Percent type for gradual scaling."""
        violations = []
        for hpa in hpas:
            behavior = hpa.get("spec", {}).get("behavior", {})
            scale_up = behavior.get("scaleUp", {})
            policies = scale_up.get("policies", [])
            has_percent = any(p.get("type") == "Percent" for p in policies)
            if not has_percent:
                violations.append(
                    f"HPA/{hpa['metadata']['name']} scaleUp missing Percent policy"
                )
        assert not violations, f"HPAs missing Percent scale-up policy: {violations}"


class TestHPATargetValidation:
    """HPA target reference validation."""

    def test_hpa_targets_existing_deployments(self, hpas, deployments):
        """HPAs should target existing Deployments."""
        deployment_names = {d.get("metadata", {}).get("name") for d in deployments}
        violations = []
        for hpa in hpas:
            target = hpa.get("spec", {}).get("scaleTargetRef", {})
            target_name = target.get("name")
            if target.get("kind") == "Deployment" and target_name not in deployment_names:
                violations.append(
                    f"HPA/{hpa['metadata']['name']} targets missing Deployment: {target_name}"
                )
        assert not violations, f"HPAs targeting missing Deployments: {violations}"

    def test_hpa_target_api_version(self, hpas):
        """HPA scaleTargetRef should use apps/v1 API version."""
        violations = []
        for hpa in hpas:
            target = hpa.get("spec", {}).get("scaleTargetRef", {})
            api_version = target.get("apiVersion", "")
            if api_version and "apps/v1" not in api_version:
                violations.append(
                    f"HPA/{hpa['metadata']['name']} target uses {api_version}, expected apps/v1"
                )
        assert not violations, f"HPAs with wrong target API version: {violations}"


class TestPDBPresence:
    """PodDisruptionBudget existence and coverage checks."""

    def test_pdbs_exist(self, pdbs):
        """At least one PDB should be defined."""
        assert len(pdbs) >= 1, "No PodDisruptionBudgets found"

    def test_all_deployments_have_pdb(self, deployments, pdbs):
        """Every Deployment should have a PDB."""
        pdb_selectors = set()
        for pdb in pdbs:
            selector = pdb.get("spec", {}).get("selector", {}).get("matchLabels", {})
            # PDBs use selectors, not direct names - check by label match
            pdb_selectors.add(tuple(sorted(selector.items())))
        # Check that each deployment's labels match at least one PDB selector
        violations = []
        for dep in deployments:
            dep_labels = dep.get("spec", {}).get("selector", {}).get("matchLabels", {})
            dep_key = tuple(sorted(dep_labels.items()))
            if dep_key not in pdb_selectors:
                violations.append(
                    f"Deployment/{dep['metadata']['name']} has no matching PDB"
                )
        assert not violations, f"Deployments without PDB: {violations}"

    def test_pdbs_in_correct_namespace(self, pdbs, namespace):
        """PDBs should be in the data-center-commander namespace."""
        ns_name = namespace.get("metadata", {}).get("name", "data-center-commander") if namespace else "data-center-commander"
        violations = []
        for pdb in pdbs:
            pdb_ns = pdb.get("metadata", {}).get("namespace")
            if pdb_ns and pdb_ns != ns_name:
                violations.append(
                    f"PDB/{pdb['metadata']['name']} in wrong namespace: {pdb_ns}"
                )
        assert not violations, f"PDBs in wrong namespace: {violations}"

    def test_pdbs_have_labels(self, pdbs):
        """PDBs should have labels."""
        violations = []
        for pdb in pdbs:
            labels = pdb.get("metadata", {}).get("labels", {})
            if not labels:
                violations.append(
                    f"PDB/{pdb['metadata']['name']} has no labels"
                )
        assert not violations, f"Unlabeled PDBs found: {violations}"


class TestPDBConfiguration:
    """PDB configuration checks."""

    def test_pdb_min_available_at_least_1(self, pdbs):
        """PDB minAvailable should be at least 1."""
        violations = []
        for pdb in pdbs:
            min_available = pdb.get("spec", {}).get("minAvailable")
            if min_available is None:
                violations.append(
                    f"PDB/{pdb['metadata']['name']} has no minAvailable"
                )
            elif min_available < 1:
                violations.append(
                    f"PDB/{pdb['metadata']['name']} minAvailable < 1: {min_available}"
                )
        assert not violations, f"PDBs with invalid minAvailable: {violations}"

    def test_pdb_uses_policy_v1(self, pdbs):
        """PDBs should use policy/v1 API version."""
        violations = []
        for pdb in pdbs:
            api_version = pdb.get("apiVersion", "")
            if "policy/v1" not in api_version:
                violations.append(
                    f"PDB/{pdb['metadata']['name']} uses {api_version}, expected policy/v1"
                )
        assert not violations, f"PDBs with wrong API version: {violations}"

    def test_pdb_has_selector(self, pdbs):
        """PDBs should have a selector."""
        violations = []
        for pdb in pdbs:
            selector = pdb.get("spec", {}).get("selector", {})
            if not selector:
                violations.append(
                    f"PDB/{pdb['metadata']['name']} has no selector"
                )
        assert not violations, f"PDBs without selector: {violations}"


class TestScalingIntegration:
    """Integration checks between HPA, PDB, and Deployments."""

    def test_hpa_pdb_coexist_for_same_deployment(self, hpas, pdbs, deployments):
        """Deployments with HPA should also have PDB for availability."""
        hpa_targets = set()
        for hpa in hpas:
            target = hpa.get("spec", {}).get("scaleTargetRef", {})
            if target.get("kind") == "Deployment":
                hpa_targets.add(target.get("name"))
        pdb_selectors = set()
        for pdb in pdbs:
            selector = pdb.get("spec", {}).get("selector", {}).get("matchLabels", {})
            pdb_selectors.add(tuple(sorted(selector.items())))
        violations = []
        for dep in deployments:
            dep_name = dep.get("metadata", {}).get("name")
            dep_labels = dep.get("spec", {}).get("selector", {}).get("matchLabels", {})
            dep_key = tuple(sorted(dep_labels.items()))
            if dep_name in hpa_targets and dep_key not in pdb_selectors:
                violations.append(
                    f"Deployment/{dep_name} has HPA but no PDB"
                )
        assert not violations, f"Deployments with HPA but no PDB: {violations}"

    def test_deployment_replicas_match_hpa_min(self, deployments, hpas):
        """Deployment replicas should be >= HPA minReplicas."""
        hpa_mins = {}
        for hpa in hpas:
            target = hpa.get("spec", {}).get("scaleTargetRef", {})
            if target.get("kind") == "Deployment":
                hpa_mins[target.get("name")] = hpa.get("spec", {}).get("minReplicas", 1)
        violations = []
        for dep in deployments:
            dep_name = dep.get("metadata", {}).get("name")
            if dep_name in hpa_mins:
                replicas = dep.get("spec", {}).get("replicas", 1)
                if replicas < hpa_mins[dep_name]:
                    violations.append(
                        f"Deployment/{dep_name} replicas ({replicas}) < HPA minReplicas ({hpa_mins[dep_name]})"
                    )
        assert not violations, f"Deployments with replicas < HPA min: {violations}"
