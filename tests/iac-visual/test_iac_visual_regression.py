"""Pytest wrapper for IaC & compliance visual regression tests.

Runs the Node.js IaC visual regression script and parses its JSON summary.
Requires: npm install (playwright, pixelmatch, pngjs)
Requires: API server running on DCC_BASE_URL (default http://127.0.0.1:8790)
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

VISUAL_DIR = Path(__file__).parent
SUMMARY_FILE = VISUAL_DIR / "summary.json"
SCRIPT = VISUAL_DIR / "iac_visual_regression.js"

BASE_URL = os.environ.get("DCC_BASE_URL", "http://127.0.0.1:8790")


def _run_visual_regression(update_baseline: bool = False) -> dict:
    """Run the Node.js IaC visual regression script and return the summary."""
    if not SCRIPT.exists():
        pytest.skip(f"IaC visual regression script not found: {SCRIPT}")

    cmd = ["node", str(SCRIPT)]
    if update_baseline:
        cmd.append("--update-baseline")

    env = os.environ.copy()
    env["DCC_BASE_URL"] = BASE_URL

    # summary.json is tracked in git, so a previous run's file is always on disk.
    # Without removing it, a harness that exits before producing results (server
    # down -> exit 2) was scored against the last good summary and reported green
    # with no server running at all. Delete it first: a summary now proves this
    # run wrote one.
    SUMMARY_FILE.unlink(missing_ok=True)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
        cwd=str(VISUAL_DIR.parent),
    )

    if not SUMMARY_FILE.exists():
        pytest.fail(
            f"IaC visual regression did not produce a summary (node exit {result.returncode}).\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    summary = json.loads(SUMMARY_FILE.read_text())
    # 0 = every view passed (or baselines were saved), 1 = view-level failures,
    # which the assertions below report per view. Anything else is the harness
    # itself failing (2 = application never answered /healthz), and a summary
    # cannot make that green.
    if result.returncode not in (0, 1):
        pytest.fail(
            f"IaC visual regression exited {result.returncode}.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    return summary


@pytest.fixture(scope="session")
def iac_visual_summary():
    """Run IaC visual regression once per test session."""
    return _run_visual_regression()


def test_iac_visual_regression_script_exists():
    """The IaC visual regression script must exist."""
    assert SCRIPT.exists(), f"Missing: {SCRIPT}"


def test_all_iac_views_have_baselines(iac_visual_summary):
    """Every IaC/compliance view must have a baseline image."""
    no_baseline = [r for r in iac_visual_summary["results"] if r["status"] == "no_baseline"]
    assert not no_baseline, f"Missing baselines for: {[r['view'] for r in no_baseline]}"


def test_no_iac_view_errors(iac_visual_summary):
    """No IaC/compliance view should error during screenshot capture."""
    errors = [r for r in iac_visual_summary["results"] if r["status"] == "error"]
    assert not errors, f"Errors in: {[r['view'] for r in errors]}"


def test_iac_visual_regression_passes(iac_visual_summary):
    """All IaC/compliance views must match their baselines within the diff threshold."""
    failures = [r for r in iac_visual_summary["results"] if r["status"] == "fail"]
    assert not failures, (
        f"IaC visual regression failed for {len(failures)} view(s):\n"
        + "\n".join(
            f"  {r['view']}: {r.get('diffFraction', '?'):.2%} diff"
            + (f" ({r.get('error', '')})" if r.get("error") else "")
            for r in failures
        )
    )


def test_iac_diff_threshold_configured(iac_visual_summary):
    """The diff threshold must be set to a reasonable value."""
    assert iac_visual_summary["diffThreshold"] <= 0.05, (
        "Diff threshold should be ≤ 5% to catch meaningful changes"
    )
