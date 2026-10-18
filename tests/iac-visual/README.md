# IaC & Compliance Visual Regression Tests

Visual regression testing for the Data Center Commander IaC dashboards and compliance dashboards. Screenshots every view and compares against baseline images using pixel-level diffing.

## Prerequisites

```bash
cd tests/iac-visual
npm install          # installs playwright, pixelmatch, pngjs
```

The API server must be running:

```bash
# Terminal 1 — start the API
python -c "from dcc.api import serve; serve()"

# Terminal 2 — run IaC visual tests
node tests/iac-visual/iac_visual_regression.js              # compare against baselines
node tests/iac-visual/iac_visual_regression.js --update-baseline  # regenerate baselines
```

## Via pytest

```bash
# Run all IaC visual tests (requires API server running)
pytest tests/iac-visual/

# With a custom API URL
DCC_BASE_URL=http://127.0.0.1:9000 pytest tests/iac-visual/
```

## Directory Structure

```
tests/iac-visual/
├── baseline/           # Committed baseline images (one per view)
├── screenshots/        # Latest screenshots (gitignored)
├── diffs/              # Diff images for failed comparisons (gitignored)
├── summary.json        # JSON results from the last run (gitignored)
├── iac_visual_regression.js  # Node.js screenshot + comparison script
└── test_iac_visual_regression.py  # Pytest wrapper
```

## Views Covered

### IaC Dashboards

| View | Description |
|------|-------------|
| `economics` | Cost intelligence, TCO, variance analysis |
| `placement` | On-premises vs cloud subscription tradeoffs |
| `forecast` | Forecast vs actual, confidence intervals, error metrics |
| `assets` | Estate & lifecycle (contains topology graph) |

### Compliance Dashboards

| View | Description |
|------|-------------|
| `security` | Security monitoring, auth events, policy violations |
| `ops` | Operations monitoring, health, alerts, SLO status |
| `quality` | Data quality scores, anomaly alerts, freshness |

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
node tests/iac-visual/iac_visual_regression.js --update-baseline
git add tests/iac-visual/baseline/
git commit -m "Update IaC visual baselines for <change>"
```

## CI Integration

```yaml
- name: IaC & Compliance Visual Regression
  run: |
    npm ci
    python -c "from dcc.api import serve; serve()" &
    sleep 2
    node tests/iac-visual/iac_visual_regression.js
```
