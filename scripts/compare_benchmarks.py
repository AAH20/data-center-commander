#!/usr/bin/env python3
"""Compare benchmark results against a baseline to detect regressions.

Usage:
    python scripts/compare_benchmarks.py \
        --baseline .benchmarks/baseline.json \
        --current .benchmarks/results.json \
        --threshold 1.5 \
        --output .benchmarks/comparison.md

Outputs:
    - A markdown report at --output path
    - A JSON summary at --output path (with .json extension)

Exit codes:
    0 = no regression detected
    1 = regression detected
    2 = error (missing files, invalid JSON, etc.)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    """Load and validate a benchmark results file."""
    with open(path) as f:
        data = json.load(f)
    if "benchmarks" not in data:
        raise ValueError(f"Missing 'benchmarks' key in {path}")
    return data


def compare_benchmarks(
    baseline: dict[str, Any],
    current: dict[str, Any],
    threshold: float = 1.5,
) -> dict[str, Any]:
    """Compare current benchmark results against a baseline.

    Args:
        baseline: Baseline benchmark results
        current: Current benchmark results
        threshold: Regression threshold (e.g., 1.5 = 50% slower)

    Returns:
        Dict with comparison results
    """
    baseline_benchmarks = baseline.get("benchmarks", {})
    current_benchmarks = current.get("benchmarks", {})

    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []
    unchanged: list[dict[str, Any]] = []
    new_benchmarks: list[str] = []
    removed_benchmarks: list[str] = []
    errors: list[str] = []

    # Find new and removed benchmarks
    baseline_names = set(baseline_benchmarks.keys())
    current_names = set(current_benchmarks.keys())

    new_benchmarks = sorted(current_names - baseline_names)
    removed_benchmarks = sorted(baseline_names - current_names)

    # Compare common benchmarks
    for name in sorted(baseline_names & current_names):
        b_result = baseline_benchmarks[name]
        c_result = current_benchmarks[name]

        if "error" in b_result or "error" in c_result:
            errors.append(name)
            continue

        b_mean = b_result["mean_seconds"]
        c_mean = c_result["mean_seconds"]

        if b_mean == 0:
            ratio = float("inf") if c_mean > 0 else 1.0
        else:
            ratio = c_mean / b_mean

        change_pct = (ratio - 1.0) * 100

        entry = {
            "name": name,
            "baseline_mean": b_mean,
            "current_mean": c_mean,
            "ratio": ratio,
            "change_pct": change_pct,
        }

        if ratio > threshold:
            regressions.append(entry)
        elif ratio < 1.0 / threshold:
            improvements.append(entry)
        else:
            unchanged.append(entry)

    regression_detected = len(regressions) > 0

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "threshold": threshold,
        "regression_detected": regression_detected,
        "total_compared": len(baseline_names & current_names),
        "regressions": regressions,
        "improvements": improvements,
        "unchanged": unchanged,
        "new_benchmarks": new_benchmarks,
        "removed_benchmarks": removed_benchmarks,
        "errors": errors,
    }


def generate_markdown_report(comparison: dict[str, Any]) -> str:
    """Generate a markdown report from comparison results."""
    lines: list[str] = []
    lines.append("# Benchmark Comparison Report")
    lines.append("")
    lines.append(f"**Timestamp:** {comparison['timestamp']}")
    lines.append(f"**Threshold:** {comparison['threshold']:.1f}x")
    lines.append(f"**Regression detected:** {'YES' if comparison['regression_detected'] else 'NO'}")
    lines.append("")

    if comparison["regressions"]:
        lines.append("## Regressions")
        lines.append("")
        lines.append("| Benchmark | Baseline (ms) | Current (ms) | Change |")
        lines.append("|-----------|---------------|--------------|--------|")
        for r in comparison["regressions"]:
            lines.append(
                f"| {r['name']} | {r['baseline_mean']*1000:.3f} | "
                f"{r['current_mean']*1000:.3f} | +{r['change_pct']:.1f}% |"
            )
        lines.append("")

    if comparison["improvements"]:
        lines.append("## Improvements")
        lines.append("")
        lines.append("| Benchmark | Baseline (ms) | Current (ms) | Change |")
        lines.append("|-----------|---------------|--------------|--------|")
        for i in comparison["improvements"]:
            lines.append(
                f"| {i['name']} | {i['baseline_mean']*1000:.3f} | "
                f"{i['current_mean']*1000:.3f} | {i['change_pct']:.1f}% |"
            )
        lines.append("")

    if comparison["unchanged"]:
        lines.append("## Unchanged")
        lines.append("")
        lines.append("| Benchmark | Baseline (ms) | Current (ms) | Change |")
        lines.append("|-----------|---------------|--------------|--------|")
        for u in comparison["unchanged"]:
            lines.append(
                f"| {u['name']} | {u['baseline_mean']*1000:.3f} | "
                f"{u['current_mean']*1000:.3f} | {u['change_pct']:+.1f}% |"
            )
        lines.append("")

    if comparison["new_benchmarks"]:
        lines.append("## New Benchmarks")
        lines.append("")
        for name in comparison["new_benchmarks"]:
            lines.append(f"- {name}")
        lines.append("")

    if comparison["removed_benchmarks"]:
        lines.append("## Removed Benchmarks")
        lines.append("")
        for name in comparison["removed_benchmarks"]:
            lines.append(f"- {name}")
        lines.append("")

    if comparison["errors"]:
        lines.append("## Errors")
        lines.append("")
        for name in comparison["errors"]:
            lines.append(f"- {name}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare benchmark results")
    parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="Path to baseline benchmark results",
    )
    parser.add_argument(
        "--current",
        type=Path,
        required=True,
        help="Path to current benchmark results",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=1.5,
        help="Regression threshold (default: 1.5 = 50%% slower)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".benchmarks/comparison.md"),
        help="Output path for markdown report",
    )
    args = parser.parse_args()

    # Load files
    try:
        baseline = load_json(args.baseline)
    except Exception as e:
        print(f"Error loading baseline: {e}", file=sys.stderr)
        return 2

    try:
        current = load_json(args.current)
    except Exception as e:
        print(f"Error loading current: {e}", file=sys.stderr)
        return 2

    # Compare
    comparison = compare_benchmarks(baseline, current, args.threshold)

    # Generate markdown report
    report = generate_markdown_report(comparison)

    # Write outputs
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        f.write(report)

    json_output = args.output.with_suffix(".json")
    with open(json_output, "w") as f:
        json.dump(comparison, f, indent=2)

    # Print summary
    print(f"Compared {comparison['total_compared']} benchmarks")
    print(f"Regressions: {len(comparison['regressions'])}")
    print(f"Improvements: {len(comparison['improvements'])}")
    print(f"Unchanged: {len(comparison['unchanged'])}")
    print(f"New: {len(comparison['new_benchmarks'])}")
    print(f"Removed: {len(comparison['removed_benchmarks'])}")
    print(f"Errors: {len(comparison['errors'])}")
    print()
    print(f"Report written to {args.output}")
    print(f"JSON summary written to {json_output}")

    if comparison["regression_detected"]:
        print()
        print("REGRESSION DETECTED:")
        for r in comparison["regressions"]:
            print(f"  {r['name']}: {r['change_pct']:+.1f}% slower")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
