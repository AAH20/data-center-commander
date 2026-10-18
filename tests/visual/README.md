# Visual Regression Tests

Visual regression testing for the Data Center Commander UI. Screenshots every view and compares against baseline images using pixel-level diffing.

## Prerequisites

```bash
cd tests/visual
npm install          # installs playwright, pixelmatch, pngjs
```

The API server must be running:

```bash
# Terminal 1 — start the API
python -c "from dcc.api import serve; serve()"

# Terminal 2 — run visual tests
node tests/visual/visual_regression.js              # compare against baselines
node tests/visual/visual_regression.js --update-baseline  # regenerate baselines
```

## Via pytest

```bash
# Run all visual tests (requires API server running)
pytest tests/visual/

# With a custom API URL
DCC_BASE_URL=http://127.0.0.1:9000 pytest tests/visual/
```

## Directory Structure

```
tests/visual/
├── baseline/           # Committed baseline images (one per view)
├── screenshots/        # Latest screenshots (gitignored)
├── diffs/              # Diff images for failed comparisons (gitignored)
├── summary.json        # JSON results from the last run (gitignored)
├── visual_regression.js  # Node.js screenshot + comparison script
└── test_visual_regression.py  # Pytest wrapper
```

## Views Covered

| View | Description |
|------|-------------|
| `overview` | Facility command picture (default) |
| `energy` | Energy, cost & carbon |
| `analytics` | Data science & continuous BI |
| `finance` | Sizing & economics |
| `capacity` | Capacity & resilience |
| `assets` | Estate & lifecycle |
| `reliability` | Reliability & maintenance |
| `workflows` | Lifecycle operations queue |
| `integrations` | Integrations & source health |
| `evidence` | Evidence & audit |
| `workloads` | Suggested workload blueprints |
| `critical` | Critical environments & GRC |

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `DCC_BASE_URL` | `http://127.0.0.1:8790` | API server URL |
| `VIEWPORT` | 1440×900 | Browser viewport |
| `PIXEL_THRESHOLD` | 0.1 | Per-pixel colour tolerance (0–1) |
| `DIFF_THRESHOLD` | 0.01 | Max fraction of pixels allowed to differ (1%) |

## Updating Baselines

When intentional UI changes are made:

```bash
node tests/visual/visual_regression.js --update-baseline
git add tests/visual/baseline/
git commit -m "Update visual baselines for <change>"
```

## CI Integration

```yaml
- name: Visual regression
  run: |
    npm ci
    python -c "from dcc.api import serve; serve()" &
    sleep 2
    node tests/visual/visual_regression.js
```
