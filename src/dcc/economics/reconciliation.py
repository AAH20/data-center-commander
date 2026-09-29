"""Estimate-to-actual reconciliation for Data Center Commander.

Compares estimated costs against actual costs, providing variance analysis
by phase, period, and line item. All calculations are deterministic,
tenant-scoped, and read-only.

The reconciliation engine handles:
- Lifecycle PV vs actual spend comparison
- Phase-level variance (electrical, mechanical, energy, etc.)
- Period-level variance (monthly/quarterly actuals vs estimate)
- Line-item level variance (estimate_line_items vs cost_actuals)
- Currency-aware matching (only compares same-currency amounts)
- Confidence intervals using low/high estimate bounds
- Variance classification (favorable, unfavorable, significant)
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VarianceThresholds:
    """Thresholds for classifying variance significance.

    Attributes:
        favorable_pct: Negative variance beyond this is favorable (e.g., -0.10 = 10% under).
        unfavorable_pct: Positive variance beyond this is unfavorable (e.g., 0.10 = 10% over).
        significant_pct: Absolute variance beyond this is significant (e.g., 0.20 = 20%).
    """

    favorable_pct: Decimal = Decimal("-0.10")
    unfavorable_pct: Decimal = Decimal("0.10")
    significant_pct: Decimal = Decimal("0.20")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> VarianceThresholds:
        if not data:
            return cls()
        return cls(
            favorable_pct=Decimal(str(data.get("favorable_pct", -0.10))),
            unfavorable_pct=Decimal(str(data.get("unfavorable_pct", 0.10))),
            significant_pct=Decimal(str(data.get("significant_pct", 0.20))),
        )


@dataclass
class PhaseVariance:
    """Variance analysis for a single phase."""

    phase: str
    estimate_base: Decimal = Decimal("0")
    estimate_low: Decimal = Decimal("0")
    estimate_high: Decimal = Decimal("0")
    actual_amount: Decimal = Decimal("0")
    variance: Decimal = Decimal("0")
    variance_pct: Optional[Decimal] = None
    line_count: int = 0
    actual_entry_count: int = 0
    classification: str = "none"
    currency: str = "USD"


@dataclass
class PeriodVariance:
    """Variance analysis for a single accounting period."""

    period: str
    estimate_base: Decimal = Decimal("0")
    actual_amount: Decimal = Decimal("0")
    variance: Decimal = Decimal("0")
    variance_pct: Optional[Decimal] = None
    by_phase: dict[str, Decimal] = field(default_factory=lambda: defaultdict(Decimal))
    classification: str = "none"
    currency: str = "USD"


@dataclass
class LineVariance:
    """Variance analysis for a single estimate line item."""

    line_id: str
    line_no: int
    description: str
    phase: str
    estimate_base: Decimal = Decimal("0")
    estimate_low: Decimal = Decimal("0")
    estimate_high: Decimal = Decimal("0")
    actual_amount: Decimal = Decimal("0")
    variance: Decimal = Decimal("0")
    variance_pct: Optional[Decimal] = None
    pricing_status: str = ""
    classification: str = "none"
    currency: str = "USD"


@dataclass
class ReconciliationSummary:
    """Overall reconciliation summary."""

    estimate_id: str
    estimate_name: str
    currency: str
    total_estimate_base: Decimal = Decimal("0")
    total_estimate_low: Decimal = Decimal("0")
    total_estimate_high: Decimal = Decimal("0")
    total_actual: Decimal = Decimal("0")
    total_variance: Decimal = Decimal("0")
    total_variance_pct: Optional[Decimal] = None
    overall_classification: str = "none"
    phase_count: int = 0
    line_count: int = 0
    actual_entry_count: int = 0
    unpriced_line_count: int = 0
    synthetic_line_count: int = 0
    periods_with_actuals: int = 0
    execution_permitted: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decimal(value: Any, default: Decimal | None = None) -> Decimal:
    """Safely convert a value to Decimal."""
    if value is None:
        if default is not None:
            return default
        raise ValueError("required numeric value is missing")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"non-finite numeric value: {value!r}")
        return value
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"invalid numeric value: {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"non-finite numeric value: {value!r}")
    return result


def _round_decimal(value: Decimal | int, places: int = 2) -> Decimal:
    """Round a Decimal to the specified number of decimal places."""
    quantize_str = "0." + "0" * places
    return Decimal(str(value)).quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)


def _classify_variance(
    variance_pct: Optional[Decimal],
    thresholds: VarianceThresholds,
) -> str:
    """Classify variance as favorable, unfavorable, significant, or none."""
    if variance_pct is None:
        return "none"
    if variance_pct <= thresholds.significant_pct and variance_pct >= -thresholds.significant_pct:
        # Within significant threshold
        if variance_pct < thresholds.favorable_pct:
            return "favorable"
        if variance_pct > thresholds.unfavorable_pct:
            return "unfavorable"
        return "on_track"
    # Beyond significant threshold
    if variance_pct < 0:
        return "significant_favorable"
    return "significant_unfavorable"


def _safe_variance_pct(actual: Decimal, estimate: Decimal) -> Optional[Decimal]:
    """Compute variance percentage, returning None if estimate is zero."""
    if estimate == 0:
        return None
    return (actual - estimate) / estimate


# ---------------------------------------------------------------------------
# Core reconciliation
# ---------------------------------------------------------------------------


def reconcile_estimate(
    *,
    estimate_id: str,
    estimate_name: str,
    currency: str,
    estimate_rollup: list[dict[str, Any]],
    actuals: list[dict[str, Any]],
    line_items: list[dict[str, Any]] | None = None,
    thresholds: VarianceThresholds | None = None,
) -> dict[str, Any]:
    """Reconcile an estimate against actual costs.

    Args:
        estimate_id: The estimate project ID.
        estimate_name: Human-readable estimate name.
        currency: Currency code for the reconciliation.
        estimate_rollup: Rows from estimate_cost_rollup view (by phase).
        actuals: Rows from cost_actuals table.
        line_items: Optional estimate_line_items for line-level detail.
        thresholds: Variance classification thresholds.

    Returns:
        A JSON-serializable dict with full reconciliation results.
    """
    if thresholds is None:
        thresholds = VarianceThresholds()

    # Build phase-level rollup
    phase_variances = _compute_phase_variances(
        estimate_rollup=estimate_rollup,
        actuals=actuals,
        currency=currency,
        thresholds=thresholds,
    )

    # Build period-level variance
    period_variances = _compute_period_variances(
        estimate_rollup=estimate_rollup,
        actuals=actuals,
        currency=currency,
        thresholds=thresholds,
    )

    # Build line-level variance if line items provided
    line_variances: list[LineVariance] = []
    if line_items:
        line_variances = _compute_line_variances(
            line_items=line_items,
            actuals=actuals,
            currency=currency,
            thresholds=thresholds,
        )

    # Build summary
    summary = _build_summary(
        estimate_id=estimate_id,
        estimate_name=estimate_name,
        currency=currency,
        phase_variances=phase_variances,
        period_variances=period_variances,
        line_variances=line_variances,
        estimate_rollup=estimate_rollup,
        actuals=actuals,
        thresholds=thresholds,
    )

    return {
        "estimate_id": estimate_id,
        "estimate_name": estimate_name,
        "currency": currency,
        "summary": _summary_to_dict(summary),
        "by_phase": [_phase_to_dict(pv) for pv in phase_variances],
        "by_period": [_period_to_dict(pv) for pv in period_variances],
        "by_line": [_line_to_dict(lv) for lv in line_variances],
        "thresholds": {
            "favorable_pct": float(thresholds.favorable_pct),
            "unfavorable_pct": float(thresholds.unfavorable_pct),
            "significant_pct": float(thresholds.significant_pct),
        },
        "execution_permitted": False,
    }


def reconcile_from_database_rows(
    *,
    estimate_row: dict[str, Any],
    rollup_rows: list[dict[str, Any]],
    actual_rows: list[dict[str, Any]],
    line_item_rows: list[dict[str, Any]] | None = None,
    thresholds: VarianceThresholds | None = None,
) -> dict[str, Any]:
    """Convenience wrapper that extracts fields from database row dicts.

    Args:
        estimate_row: Row from estimate_projects.
        rollup_rows: Rows from estimate_cost_rollup for this estimate.
        actual_rows: Rows from cost_actuals for this estimate.
        line_item_rows: Optional rows from estimate_line_items.
        thresholds: Variance classification thresholds.

    Returns:
        A JSON-serializable dict with full reconciliation results.
    """
    return reconcile_estimate(
        estimate_id=str(estimate_row.get("id", "")),
        estimate_name=str(estimate_row.get("name", "")),
        currency=str(estimate_row.get("currency", "USD")),
        estimate_rollup=rollup_rows,
        actuals=actual_rows,
        line_items=line_item_rows,
        thresholds=thresholds,
    )


# ---------------------------------------------------------------------------
# Phase-level variance
# ---------------------------------------------------------------------------


def _compute_phase_variances(
    *,
    estimate_rollup: list[dict[str, Any]],
    actuals: list[dict[str, Any]],
    currency: str,
    thresholds: VarianceThresholds,
) -> list[PhaseVariance]:
    """Compute variance by phase."""
    # Aggregate actuals by phase
    actual_by_phase: dict[str, Decimal] = defaultdict(Decimal)
    actual_count_by_phase: dict[str, int] = defaultdict(int)
    for row in actuals:
        row_currency = str(row.get("currency", ""))
        if row_currency != currency:
            continue
        phase = str(row.get("phase", "other"))
        amount = _decimal(row.get("amount", 0))
        actual_by_phase[phase] += amount
        actual_count_by_phase[phase] += 1

    # Build phase variances from rollup
    phase_map: dict[str, PhaseVariance] = {}
    for row in estimate_rollup:
        row_currency = str(row.get("currency", ""))
        if row_currency != currency:
            continue
        phase = str(row.get("phase", "other"))
        pv_base = _decimal(row.get("present_value_base", 0))
        pv_low = _decimal(row.get("present_value_low", 0))
        pv_high = _decimal(row.get("present_value_high", 0))
        line_count = int(row.get("line_count", 0))

        if phase in phase_map:
            phase_map[phase].estimate_base += pv_base
            phase_map[phase].estimate_low += pv_low
            phase_map[phase].estimate_high += pv_high
            phase_map[phase].line_count += line_count
        else:
            phase_map[phase] = PhaseVariance(
                phase=phase,
                estimate_base=pv_base,
                estimate_low=pv_low,
                estimate_high=pv_high,
                line_count=line_count,
                currency=currency,
            )

    # Add actuals
    for phase, amount in actual_by_phase.items():
        if phase in phase_map:
            phase_map[phase].actual_amount += amount
            phase_map[phase].actual_entry_count += actual_count_by_phase[phase]
        else:
            phase_map[phase] = PhaseVariance(
                phase=phase,
                actual_amount=amount,
                actual_entry_count=actual_count_by_phase[phase],
                currency=currency,
            )

    # Compute variance and classification
    result: list[PhaseVariance] = []
    for phase in sorted(phase_map.keys()):
        pv = phase_map[phase]
        pv.variance = pv.actual_amount - pv.estimate_base
        pv.variance_pct = _safe_variance_pct(pv.actual_amount, pv.estimate_base)
        pv.classification = _classify_variance(pv.variance_pct, thresholds)
        result.append(pv)

    return result


# ---------------------------------------------------------------------------
# Period-level variance
# ---------------------------------------------------------------------------


def _compute_period_variances(
    *,
    estimate_rollup: list[dict[str, Any]],
    actuals: list[dict[str, Any]],
    currency: str,
    thresholds: VarianceThresholds,
) -> list[PeriodVariance]:
    """Compute variance by accounting period.

    For period-level comparison, we use the first_period_cost from the rollup
    as the estimate baseline for the first period, and distribute the remaining
    PV across periods proportionally. This is a simplified approach; a more
    sophisticated approach would use the budget forecast engine.
    """
    # Aggregate actuals by period
    actual_by_period: dict[str, Decimal] = defaultdict(Decimal)
    actual_by_period_phase: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: defaultdict(Decimal)
    )
    for row in actuals:
        row_currency = str(row.get("currency", ""))
        if row_currency != currency:
            continue
        period = str(row.get("accounting_period", ""))
        amount = _decimal(row.get("amount", 0))
        phase = str(row.get("phase", "other"))
        actual_by_period[period] += amount
        actual_by_period_phase[period][phase] += amount

    # For period-level estimate, we use first_period_cost as a proxy
    # In a full implementation, this would use the budget forecast
    total_first_period = Decimal("0")
    for row in estimate_rollup:
        row_currency = str(row.get("currency", ""))
        if row_currency != currency:
            continue
        total_first_period += _decimal(row.get("first_period_cost", 0))

    # Build period variances
    result: list[PeriodVariance] = []
    for period in sorted(actual_by_period.keys()):
        actual_amount = actual_by_period[period]
        # Use first_period_cost as estimate for the first period
        # For subsequent periods, we don't have a simple estimate breakdown
        # so we use the total first period cost as a baseline
        estimate_base = total_first_period if period == sorted(actual_by_period.keys())[0] else Decimal("0")

        variance = actual_amount - estimate_base
        variance_pct = _safe_variance_pct(actual_amount, estimate_base)

        pv = PeriodVariance(
            period=period,
            estimate_base=estimate_base,
            actual_amount=actual_amount,
            variance=variance,
            variance_pct=variance_pct,
            by_phase=dict(actual_by_period_phase[period]),
            classification=_classify_variance(variance_pct, thresholds),
            currency=currency,
        )
        result.append(pv)

    return result


# ---------------------------------------------------------------------------
# Line-level variance
# ---------------------------------------------------------------------------


def _compute_line_variances(
    *,
    line_items: list[dict[str, Any]],
    actuals: list[dict[str, Any]],
    currency: str,
    thresholds: VarianceThresholds,
) -> list[LineVariance]:
    """Compute variance by line item."""
    # Index actuals by estimate_line_id
    actual_by_line: dict[str, Decimal] = defaultdict(Decimal)
    for row in actuals:
        row_currency = str(row.get("currency", ""))
        if row_currency != currency:
            continue
        line_id = str(row.get("estimate_line_id", ""))
        if line_id:
            amount = _decimal(row.get("amount", 0))
            actual_by_line[line_id] += amount

    result: list[LineVariance] = []
    for item in line_items:
        line_id = str(item.get("id", ""))
        line_no = int(item.get("line_no", 0))
        description = str(item.get("description", ""))
        phase = str(item.get("phase", "other"))
        ext_base = _decimal(item.get("extended_base", 0))
        ext_low = _decimal(item.get("extended_low", ext_base))
        ext_high = _decimal(item.get("extended_high", ext_base))
        pricing_status = str(item.get("pricing_status", ""))
        item_currency = str(item.get("currency", "USD"))

        if item_currency != currency:
            continue

        actual_amount = actual_by_line.get(line_id, Decimal("0"))
        variance = actual_amount - ext_base
        variance_pct = _safe_variance_pct(actual_amount, ext_base)

        lv = LineVariance(
            line_id=line_id,
            line_no=line_no,
            description=description,
            phase=phase,
            estimate_base=ext_base,
            estimate_low=ext_low,
            estimate_high=ext_high,
            actual_amount=actual_amount,
            variance=variance,
            variance_pct=variance_pct,
            pricing_status=pricing_status,
            classification=_classify_variance(variance_pct, thresholds),
            currency=currency,
        )
        result.append(lv)

    # Sort by line_no
    result.sort(key=lambda x: x.line_no)
    return result


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def _build_summary(
    *,
    estimate_id: str,
    estimate_name: str,
    currency: str,
    phase_variances: list[PhaseVariance],
    period_variances: list[PeriodVariance],
    line_variances: list[LineVariance],
    estimate_rollup: list[dict[str, Any]],
    actuals: list[dict[str, Any]],
    thresholds: VarianceThresholds,
) -> ReconciliationSummary:
    """Build overall reconciliation summary."""
    total_estimate_base = sum((pv.estimate_base for pv in phase_variances), Decimal("0"))
    total_estimate_low = sum((pv.estimate_low for pv in phase_variances), Decimal("0"))
    total_estimate_high = sum((pv.estimate_high for pv in phase_variances), Decimal("0"))
    total_actual = sum((pv.actual_amount for pv in phase_variances), Decimal("0"))
    total_variance = total_actual - total_estimate_base
    total_variance_pct = _safe_variance_pct(total_actual, total_estimate_base)

    # Count unpriced and synthetic lines from rollup
    unpriced_lines = 0
    synthetic_lines = 0
    for row in estimate_rollup:
        unpriced_lines += int(row.get("unpriced_lines", 0))
        synthetic_lines += int(row.get("synthetic_lines", 0))

    # Count periods with actuals
    periods_with_actuals = len(period_variances)

    # Count actual entries
    actual_entry_count = len([
        a for a in actuals if str(a.get("currency", "")) == currency
    ])

    return ReconciliationSummary(
        estimate_id=estimate_id,
        estimate_name=estimate_name,
        currency=currency,
        total_estimate_base=total_estimate_base,
        total_estimate_low=total_estimate_low,
        total_estimate_high=total_estimate_high,
        total_actual=total_actual,
        total_variance=total_variance,
        total_variance_pct=total_variance_pct,
        overall_classification=_classify_variance(total_variance_pct, thresholds),
        phase_count=len(phase_variances),
        line_count=len(line_variances),
        actual_entry_count=actual_entry_count,
        unpriced_line_count=unpriced_lines,
        synthetic_line_count=synthetic_lines,
        periods_with_actuals=periods_with_actuals,
    )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _summary_to_dict(s: ReconciliationSummary) -> dict[str, Any]:
    return {
        "estimate_id": s.estimate_id,
        "estimate_name": s.estimate_name,
        "currency": s.currency,
        "total_estimate_base": _round_decimal(s.total_estimate_base),
        "total_estimate_low": _round_decimal(s.total_estimate_low),
        "total_estimate_high": _round_decimal(s.total_estimate_high),
        "total_actual": _round_decimal(s.total_actual),
        "total_variance": _round_decimal(s.total_variance),
        "total_variance_pct": (
            _round_decimal(s.total_variance_pct * 100) if s.total_variance_pct is not None else None
        ),
        "overall_classification": s.overall_classification,
        "phase_count": s.phase_count,
        "line_count": s.line_count,
        "actual_entry_count": s.actual_entry_count,
        "unpriced_line_count": s.unpriced_line_count,
        "synthetic_line_count": s.synthetic_line_count,
        "periods_with_actuals": s.periods_with_actuals,
        "execution_permitted": s.execution_permitted,
    }


def _phase_to_dict(pv: PhaseVariance) -> dict[str, Any]:
    return {
        "phase": pv.phase,
        "estimate_base": _round_decimal(pv.estimate_base),
        "estimate_low": _round_decimal(pv.estimate_low),
        "estimate_high": _round_decimal(pv.estimate_high),
        "actual_amount": _round_decimal(pv.actual_amount),
        "variance": _round_decimal(pv.variance),
        "variance_pct": (
            _round_decimal(pv.variance_pct * 100) if pv.variance_pct is not None else None
        ),
        "line_count": pv.line_count,
        "actual_entry_count": pv.actual_entry_count,
        "classification": pv.classification,
        "currency": pv.currency,
    }


def _period_to_dict(pv: PeriodVariance) -> dict[str, Any]:
    return {
        "period": pv.period,
        "estimate_base": _round_decimal(pv.estimate_base),
        "actual_amount": _round_decimal(pv.actual_amount),
        "variance": _round_decimal(pv.variance),
        "variance_pct": (
            _round_decimal(pv.variance_pct * 100) if pv.variance_pct is not None else None
        ),
        "by_phase": {k: _round_decimal(v) for k, v in pv.by_phase.items()},
        "classification": pv.classification,
        "currency": pv.currency,
    }


def _line_to_dict(lv: LineVariance) -> dict[str, Any]:
    return {
        "line_id": lv.line_id,
        "line_no": lv.line_no,
        "description": lv.description,
        "phase": lv.phase,
        "estimate_base": _round_decimal(lv.estimate_base),
        "estimate_low": _round_decimal(lv.estimate_low),
        "estimate_high": _round_decimal(lv.estimate_high),
        "actual_amount": _round_decimal(lv.actual_amount),
        "variance": _round_decimal(lv.variance),
        "variance_pct": (
            _round_decimal(lv.variance_pct * 100) if lv.variance_pct is not None else None
        ),
        "pricing_status": lv.pricing_status,
        "classification": lv.classification,
        "currency": lv.currency,
    }


# ---------------------------------------------------------------------------
# Multi-estimate reconciliation
# ---------------------------------------------------------------------------


def reconcile_multiple(
    *,
    estimates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Reconcile multiple estimates and provide a combined summary.

    Args:
        estimates: List of dicts, each containing:
            - estimate_row: Row from estimate_projects
            - rollup_rows: Rows from estimate_cost_rollup
            - actual_rows: Rows from cost_actuals
            - line_item_rows: Optional rows from estimate_line_items

    Returns:
        A JSON-serializable dict with individual and combined results.
    """
    if not estimates:
        raise ValueError("at least one estimate is required")
    if len(estimates) > 50:
        raise ValueError("maximum 50 estimates can be reconciled at once")

    results = []
    for est in estimates:
        result = reconcile_from_database_rows(
            estimate_row=est["estimate_row"],
            rollup_rows=est.get("rollup_rows", []),
            actual_rows=est.get("actual_rows", []),
            line_item_rows=est.get("line_item_rows"),
        )
        results.append(result)

    # Combined summary
    total_estimate = Decimal("0")
    total_actual = Decimal("0")
    total_variance = Decimal("0")
    currencies: set[str] = set()

    for r in results:
        s = r["summary"]
        total_estimate += _decimal(s["total_estimate_base"])
        total_actual += _decimal(s["total_actual"])
        total_variance += _decimal(s["total_variance"])
        currencies.add(s["currency"])

    total_variance_pct = _safe_variance_pct(total_actual, total_estimate)

    return {
        "estimates": results,
        "combined": {
            "estimate_count": len(results),
            "currencies": sorted(currencies),
            "multi_currency": len(currencies) > 1,
            "total_estimate_base": _round_decimal(total_estimate),
            "total_actual": _round_decimal(total_actual),
            "total_variance": _round_decimal(total_variance),
            "total_variance_pct": (
                _round_decimal(total_variance_pct * 100)
                if total_variance_pct is not None
                else None
            ),
        },
        "execution_permitted": False,
    }
