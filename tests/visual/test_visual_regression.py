"""Pytest wrapper for visual regression tests.

Runs the Node.js visual regression script and parses its JSON summary.
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
SCRIPT = VISUAL_DIR / "visual_regression.js"

BASE_URL = os.environ.get("DCC_BASE_URL", "http://127.0.0.1:8790")


def _run_visual_regression(update_baseline: bool = False) -> dict:
    """Run the Node.js visual regression script and return the summary."""
    if not SCRIPT.exists():
        pytest.skip(f"Visual regression script not found: {SCRIPT}")

    cmd = ["node", str(SCRIPT)]
    if update_baseline:
        cmd.append("--update-baseline")

    env = os.environ.copy()
    env["DCC_BASE_URL"] = BASE_URL

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
            f"Visual regression did not produce a summary.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    return json.loads(SUMMARY_FILE.read_text())


@pytest.fixture(scope="session")
def visual_summary():
    """Run visual regression once per test session."""
    return _run_visual_regression()


def test_visual_regression_script_exists():
    """The visual regression script must exist."""
    assert SCRIPT.exists(), f"Missing: {SCRIPT}"


def test_all_views_have_baselines(visual_summary):
    """Every view must have a baseline image."""
    no_baseline = [r for r in visual_summary["results"] if r["status"] == "no_baseline"]
    assert not no_baseline, f"Missing baselines for: {[r['view'] for r in no_baseline]}"


def test_no_view_errors(visual_summary):
    """No view should error during screenshot capture."""
    errors = [r for r in visual_summary["results"] if r["status"] == "error"]
    assert not errors, f"Errors in: {[r['view'] for r in errors]}"


def test_visual_regression_passes(visual_summary):
    """All views must match their baselines within the diff threshold."""
    failures = [r for r in visual_summary["results"] if r["status"] == "fail"]
    assert not failures, (
        f"Visual regression failed for {len(failures)} view(s):\n"
        + "\n".join(
            f"  {r['view']}: {r.get('diffFraction', '?'):.2%} diff"
            + (f" ({r.get('error', '')})" if r.get("error") else "")
            for r in failures
        )
    )


def test_diff_threshold_configured(visual_summary):
    """The diff threshold must be set to a reasonable value."""
    assert visual_summary["diffThreshold"] <= 0.05, (
        "Diff threshold should be ≤ 5% to catch meaningful changes"
    )
