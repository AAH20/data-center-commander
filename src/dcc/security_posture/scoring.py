"""Cloud security scoring engine.

Scores security posture across multiple dimensions: identity & access,
data protection, network security, logging & monitoring, and
infrastructure security. Produces a weighted 0-100 score with
per-dimension breakdowns and recommendations.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class PostureDimension(str, Enum):
    """Security posture dimensions."""
    IDENTITY_ACCESS = "identity_access"
    DATA_PROTECTION = "data_protection"
    NETWORK_SECURITY = "network_security"
    LOGGING_MONITORING = "logging_monitoring"
    INFRASTRUCTURE_SECURITY = "infrastructure_security"


class ControlStatus(str, Enum):
    """Status of an individual security control."""
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    NOT_ASSESSED = "not_assessed"


DEFAULT_DIMENSION_WEIGHTS: dict[PostureDimension, float] = {
    PostureDimension.IDENTITY_ACCESS: 0.25,
    PostureDimension.DATA_PROTECTION: 0.25,
    PostureDimension.NETWORK_SECURITY: 0.20,
    PostureDimension.LOGGING_MONITORING: 0.15,
    PostureDimension.INFRASTRUCTURE_SECURITY: 0.15,
}


@dataclass(frozen=True)
class PostureScore:
    """Score for a single posture dimension."""
    dimension: PostureDimension
    score: float  # 0.0 - 1.0
    weight: float
    passed: int = 0
    failed: int = 0
    partial: int = 0
    not_assessed: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def weighted(self) -> float:
        return self.score * self.weight

    @property
    def total_controls(self) -> int:
        return self.passed + self.failed + self.partial + self.not_assessed


@dataclass
class PostureReport:
    """Aggregated security posture report."""
    overall_score: float  # 0-100
    dimension_scores: dict[PostureDimension, PostureScore]
    graded_at: str
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 2),
            "graded_at": self.graded_at,
            "dimensions": {
                dim.value: {
                    "score": round(s.score, 4),
                    "weight": s.weight,
                    "weighted": round(s.weighted, 4),
                    "passed": s.passed,
                    "failed": s.failed,
                    "partial": s.partial,
                    "not_assessed": s.not_assessed,
                    "total_controls": s.total_controls,
                    "details": s.details,
                }
                for dim, s in self.dimension_scores.items()
            },
            "recommendations": self.recommendations,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class ControlResult:
    """Result of evaluating a single security control."""
    name: str
    dimension: PostureDimension
    status: ControlStatus
    weight: float = 1.0
    description: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


class SecurityScoringEngine:
    """Evaluates security posture across all dimensions.

    Controls are registered per-dimension with a check callable that
    returns a :class:`ControlResult`. The engine aggregates results
    into dimension scores and an overall 0-100 score.
    """

    def __init__(
        self,
        weights: dict[PostureDimension, float] | None = None,
    ) -> None:
        self.weights = weights or DEFAULT_DIMENSION_WEIGHTS.copy()
        self._controls: dict[PostureDimension, list[tuple[str, Callable[[], ControlResult]]]] = {
            dim: [] for dim in PostureDimension
        }

    def register_control(
        self,
        dimension: PostureDimension,
        name: str,
        check: Callable[[], ControlResult],
    ) -> None:
        """Register a security control check."""
        self._controls[dimension].append((name, check))

    def evaluate(self, metadata: dict[str, Any] | None = None) -> PostureReport:
        """Run all registered controls and produce a posture report."""
        dimension_scores: dict[PostureDimension, PostureScore] = {}

        for dim in PostureDimension:
            controls = self._controls[dim]
            if not controls:
                dimension_scores[dim] = PostureScore(
                    dimension=dim,
                    score=0.0,
                    weight=self.weights[dim],
                    not_assessed=1,
                    details={"note": "no controls registered"},
                )
                continue

            passed = failed = partial = not_assessed = 0
            control_details: dict[str, Any] = {}

            for name, check in controls:
                try:
                    result = check()
                except Exception as exc:
                    result = ControlResult(
                        name=name,
                        dimension=dim,
                        status=ControlStatus.NOT_ASSESSED,
                        description=f"check failed: {exc}",
                    )

                control_details[name] = {
                    "status": result.status.value,
                    "description": result.description,
                    "evidence": result.evidence,
                }

                if result.status == ControlStatus.PASS:
                    passed += 1
                elif result.status == ControlStatus.FAIL:
                    failed += 1
                elif result.status == ControlStatus.PARTIAL:
                    partial += 1
                else:
                    not_assessed += 1

            total = passed + failed + partial + not_assessed
            if total == 0:
                score = 0.0
            else:
                # Weighted: pass=1.0, partial=0.5, fail=0.0, not_assessed=0.0
                score = (passed + partial * 0.5) / total

            dimension_scores[dim] = PostureScore(
                dimension=dim,
                score=score,
                weight=self.weights[dim],
                passed=passed,
                failed=failed,
                partial=partial,
                not_assessed=not_assessed,
                details={"controls": control_details},
            )

        overall = sum(s.weighted for s in dimension_scores.values()) * 100
        recommendations = self._generate_recommendations(dimension_scores)

        return PostureReport(
            overall_score=round(overall, 2),
            dimension_scores=dimension_scores,
            graded_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            recommendations=recommendations,
            metadata=metadata or {},
        )

    def _generate_recommendations(
        self,
        scores: dict[PostureDimension, PostureScore],
    ) -> list[str]:
        recs: list[str] = []
        for dim, s in scores.items():
            if s.score < 0.5:
                recs.append(
                    f"{dim.value}: critical — score {s.score:.0%} "
                    f"({s.failed} failed controls)"
                )
            elif s.score < 0.8:
                recs.append(
                    f"{dim.value}: needs improvement — score {s.score:.0%} "
                    f"({s.failed} failed, {s.partial} partial)"
                )
        return recs


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def score_cloud_security(
    checks: dict[PostureDimension, list[tuple[str, Callable[[], ControlResult]]]] | None = None,
    metadata: dict[str, Any] | None = None,
    weights: dict[PostureDimension, float] | None = None,
) -> PostureReport:
    """Convenience wrapper to score cloud security posture.

    Parameters
    ----------
    checks:
        Mapping of dimension → list of (name, check_callable) tuples.
    metadata:
        Optional metadata to include in the report.
    weights:
        Optional custom dimension weights.
    """
    engine = SecurityScoringEngine(weights=weights)
    if checks:
        for dim, controls in checks.items():
            for name, check in controls:
                engine.register_control(dim, name, check)
    return engine.evaluate(metadata=metadata)
