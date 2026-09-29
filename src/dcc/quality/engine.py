"""Data quality scoring engine: completeness, freshness, consistency, accuracy."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class QualityDimension(str, Enum):
    COMPLETENESS = "completeness"
    FRESHNESS = "freshness"
    CONSISTENCY = "consistency"
    ACCURACY = "accuracy"


DEFAULT_WEIGHTS: dict[QualityDimension, float] = {
    QualityDimension.COMPLETENESS: 0.30,
    QualityDimension.FRESHNESS: 0.25,
    QualityDimension.CONSISTENCY: 0.25,
    QualityDimension.ACCURACY: 0.20,
}


@dataclass(frozen=True)
class QualityScore:
    """A single dimension score with evidence."""
    dimension: QualityDimension
    score: float  # 0.0 – 1.0
    weight: float
    passed: int = 0
    total: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def weighted(self) -> float:
        return self.score * self.weight


@dataclass
class QualityReport:
    """Aggregated quality report for a data source."""
    source: str
    scores: dict[QualityDimension, QualityScore]
    overall: float
    graded_at: str
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "overall": round(self.overall, 4),
            "graded_at": self.graded_at,
            "scores": {
                dim.value: {
                    "score": round(s.score, 4),
                    "weight": s.weight,
                    "weighted": round(s.weighted, 4),
                    "passed": s.passed,
                    "total": s.total,
                    "details": s.details,
                }
                for dim, s in self.scores.items()
            },
            "recommendations": self.recommendations,
        }


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def completeness_score(
    records: list[dict[str, Any]],
    required_fields: list[str],
    optional_fields: list[str] | None = None,
) -> QualityScore:
    """Score completeness: fraction of required fields present and non-null."""
    optional_fields = optional_fields or []
    if not records:
        return QualityScore(
            dimension=QualityDimension.COMPLETENESS,
            score=0.0,
            weight=DEFAULT_WEIGHTS[QualityDimension.COMPLETENESS],
            passed=0,
            total=len(required_fields),
            details={"error": "no records"},
        )

    passed = 0
    total = 0
    field_stats: dict[str, int] = {}
    for f in required_fields:
        present = sum(1 for r in records if r.get(f) is not None and r.get(f) != "")
        field_stats[f] = present
        passed += present
        total += len(records)

    # Optional fields contribute half-weight
    optional_passed = 0
    optional_total = 0
    for f in optional_fields:
        present = sum(1 for r in records if r.get(f) is not None and r.get(f) != "")
        field_stats[f] = present
        optional_passed += present
        optional_total += len(records)

    if total == 0:
        score = 0.0
    elif optional_total == 0:
        score = _clamp(passed / total)
    else:
        required_ratio = passed / total
        optional_ratio = optional_passed / optional_total
        score = _clamp(required_ratio * 0.8 + optional_ratio * 0.2)

    return QualityScore(
        dimension=QualityDimension.COMPLETENESS,
        score=score,
        weight=DEFAULT_WEIGHTS[QualityDimension.COMPLETENESS],
        passed=passed,
        total=total,
        details={"field_stats": field_stats, "optional_passed": optional_passed, "optional_total": optional_total},
    )


def freshness_score(
    timestamps: list[dt.datetime],
    max_age_hours: float = 24.0,
    now: dt.datetime | None = None,
) -> QualityScore:
    """Score freshness: how recent the newest record is."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if not timestamps:
        return QualityScore(
            dimension=QualityDimension.FRESHNESS,
            score=0.0,
            weight=DEFAULT_WEIGHTS[QualityDimension.FRESHNESS],
            passed=0,
            total=0,
            details={"error": "no timestamps"},
        )

    # Normalize to UTC
    normalized = []
    for ts in timestamps:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=dt.timezone.utc)
        normalized.append(ts)

    newest = max(normalized)
    age_hours = (now - newest).total_seconds() / 3600.0

    if age_hours <= max_age_hours:
        score = 1.0
    elif age_hours <= max_age_hours * 7:
        # Linear decay over a week
        score = _clamp(1.0 - (age_hours - max_age_hours) / (max_age_hours * 6))
    else:
        score = 0.0

    return QualityScore(
        dimension=QualityDimension.FRESHNESS,
        score=score,
        weight=DEFAULT_WEIGHTS[QualityDimension.FRESHNESS],
        passed=1 if score > 0 else 0,
        total=1,
        details={
            "newest": newest.isoformat(),
            "age_hours": round(age_hours, 2),
            "max_age_hours": max_age_hours,
        },
    )


def consistency_score(
    records: list[dict[str, Any]],
    rules: list[Callable[[dict[str, Any]], bool]],
    rule_names: list[str] | None = None,
) -> QualityScore:
    """Score consistency: fraction of records passing all validation rules."""
    if not records:
        return QualityScore(
            dimension=QualityDimension.CONSISTENCY,
            score=0.0,
            weight=DEFAULT_WEIGHTS[QualityDimension.CONSISTENCY],
            passed=0,
            total=0,
            details={"error": "no records"},
        )

    rule_names = rule_names or [f"rule_{i}" for i in range(len(rules))]
    passed = 0
    rule_stats: dict[str, int] = {name: 0 for name in rule_names}

    for record in records:
        all_pass = True
        for rule, name in zip(rules, rule_names):
            try:
                ok = rule(record)
            except Exception:
                ok = False
            if ok:
                rule_stats[name] += 1
            else:
                all_pass = False
        if all_pass:
            passed += 1

    score = _clamp(passed / len(records))
    return QualityScore(
        dimension=QualityDimension.CONSISTENCY,
        score=score,
        weight=DEFAULT_WEIGHTS[QualityDimension.CONSISTENCY],
        passed=passed,
        total=len(records),
        details={"rule_stats": rule_stats},
    )


def accuracy_score(
    records: list[dict[str, Any]],
    reference_values: dict[str, Any],
    tolerance: float = 0.01,
) -> QualityScore:
    """Score accuracy: fraction of records matching reference values within tolerance."""
    if not records:
        return QualityScore(
            dimension=QualityDimension.ACCURACY,
            score=0.0,
            weight=DEFAULT_WEIGHTS[QualityDimension.ACCURACY],
            passed=0,
            total=0,
            details={"error": "no records"},
        )

    passed = 0
    total = 0
    field_stats: dict[str, dict[str, Any]] = {}

    for field, expected in reference_values.items():
        field_passed = 0
        field_total = 0
        for record in records:
            actual = record.get(field)
            if actual is None:
                continue
            field_total += 1
            total += 1
            if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
                if abs(float(actual) - float(expected)) <= tolerance:
                    field_passed += 1
                    passed += 1
            elif actual == expected:
                field_passed += 1
                passed += 1
        field_stats[field] = {"passed": field_passed, "total": field_total}

    score = _clamp(passed / total) if total > 0 else 0.0
    return QualityScore(
        dimension=QualityDimension.ACCURACY,
        score=score,
        weight=DEFAULT_WEIGHTS[QualityDimension.ACCURACY],
        passed=passed,
        total=total,
        details={"field_stats": field_stats, "tolerance": tolerance},
    )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class QualityEngine:
    """Orchestrates quality scoring across all four dimensions."""

    def __init__(self, weights: dict[QualityDimension, float] | None = None):
        self.weights = weights or DEFAULT_WEIGHTS.copy()

    def score_source(
        self,
        source: str,
        records: list[dict[str, Any]],
        *,
        required_fields: list[str] | None = None,
        optional_fields: list[str] | None = None,
        timestamps: list[dt.datetime] | None = None,
        max_age_hours: float = 24.0,
        consistency_rules: list[Callable[[dict[str, Any]], bool]] | None = None,
        rule_names: list[str] | None = None,
        reference_values: dict[str, Any] | None = None,
        tolerance: float = 0.01,
    ) -> QualityReport:
        """Score a data source across all four dimensions."""
        required_fields = required_fields or []
        optional_fields = optional_fields or []
        consistency_rules = consistency_rules or []
        reference_values = reference_values or {}

        scores: dict[QualityDimension, QualityScore] = {}

        # Completeness
        scores[QualityDimension.COMPLETENESS] = completeness_score(
            records, required_fields, optional_fields
        )

        # Freshness
        if timestamps:
            scores[QualityDimension.FRESHNESS] = freshness_score(timestamps, max_age_hours)
        else:
            scores[QualityDimension.FRESHNESS] = QualityScore(
                dimension=QualityDimension.FRESHNESS,
                score=0.0,
                weight=self.weights[QualityDimension.FRESHNESS],
                details={"error": "no timestamps provided"},
            )

        # Consistency
        if consistency_rules:
            scores[QualityDimension.CONSISTENCY] = consistency_score(
                records, consistency_rules, rule_names
            )
        else:
            scores[QualityDimension.CONSISTENCY] = QualityScore(
                dimension=QualityDimension.CONSISTENCY,
                score=1.0,
                weight=self.weights[QualityDimension.CONSISTENCY],
                details={"note": "no rules provided; defaulting to 1.0"},
            )

        # Accuracy
        if reference_values:
            scores[QualityDimension.ACCURACY] = accuracy_score(
                records, reference_values, tolerance
            )
        else:
            scores[QualityDimension.ACCURACY] = QualityScore(
                dimension=QualityDimension.ACCURACY,
                score=1.0,
                weight=self.weights[QualityDimension.ACCURACY],
                details={"note": "no reference values; defaulting to 1.0"},
            )

        overall = sum(s.weighted for s in scores.values())
        recommendations = self._recommendations(scores)

        return QualityReport(
            source=source,
            scores=scores,
            overall=_clamp(overall),
            graded_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            recommendations=recommendations,
        )

    def _recommendations(self, scores: dict[QualityDimension, QualityScore]) -> list[str]:
        recs: list[str] = []
        for dim, s in scores.items():
            if s.score < 0.5:
                recs.append(f"{dim.value}: critical — score {s.score:.2f}")
            elif s.score < 0.8:
                recs.append(f"{dim.value}: needs improvement — score {s.score:.2f}")
        return recs


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def score_source(
    source: str,
    records: list[dict[str, Any]],
    **kwargs: Any,
) -> QualityReport:
    """Convenience wrapper around QualityEngine.score_source."""
    engine = QualityEngine()
    return engine.score_source(source, records, **kwargs)
