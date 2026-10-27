# IaC & Compliance Visual Regression Tests

Visual regression testing for the Data Center Commander IaC dashboards and compliance dashboards. Screenshots every view and compares against baseline images using pixel-level diffing.

## Prerequisites

```bash
npm install                        # playwright, pixelmatch, pngjs (repo root package.json)
npx playwright install chromium    # the browser binary is NOT installed by npm install
```

The application must be running, and PostgreSQL must be reachable:

```bash
export PYTHONPATH=src
export DCC_DATABASE_URL=postgresql://localhost:5432/dcc_demo_local
export DCC_ALLOW_ANONYMOUS=1       # local/CI only; see "Authentication" below
.venv/bin/python scripts/run-local.py --host 127.0.0.1 --port 8790
```

`DCC_ALLOW_ANONYMOUS=1` is required because the console loads its dashboards from
`/assets/*.js`, and `/assets` is not in `_AUTH_PUBLIC_PATHS` (`src/dcc/api_async.py:605`).
With authentication enforced and no API key, every asset returns 401, the dashboard
modules never mount, and the capture fails. `tests/conftest.py:14` sets the same
variable for the same reason. In CI, prefer minting a key
(`python -m dcc.keys_cli create ...`) over running the gate anonymously.

The harness polls `/healthz` itself (30s budget) and exits 2 with the start command
when nothing answers, so **no `sleep` is needed** before running it.

```bash
node tests/iac-visual/iac_visual_regression.js                    # compare
node tests/iac-visual/iac_visual_regression.js --update-baseline  # regenerate
node tests/iac-visual/iac_visual_regression.js --view economics   # one view
```

## Via pytest

```bash
pytest tests/iac-visual/
DCC_BASE_URL=http://127.0.0.1:9000 pytest tests/iac-visual/
```

## Directory Structure

```
tests/iac-visual/
├── baseline/           # Baseline images (one per view) — COMMIT THESE
├── screenshots/        # Latest screenshots (generated; currently tracked in git)
├── diffs/              # Diff images, written only when a comparison fails
├── summary.json        # JSON results from the last run
├── iac_visual_regression.js       # Node.js screenshot + comparison script
└── test_iac_visual_regression.py  # Pytest wrapper
```

## Views Covered

| View | Description |
|------|-------------|
| `economics` | Cost intelligence, TCO, variance analysis |
| `placement` | On-premises vs cloud subscription tradeoffs |
| `forecast` | Forecast vs actual, confidence intervals, error metrics |
| `assets` | Estate & lifecycle |
| `security` | Security monitoring, auth events, policy violations |
| `ops` | Operations monitoring, health, alerts, SLO status |
| `quality` | Data quality scores, anomaly alerts, freshness |

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `DCC_BASE_URL` | `http://127.0.0.1:8790` | Application URL (wins over `--port`) |
| `VIEWPORT` | 1440×900 | Browser viewport |
| `PIXEL_THRESHOLD` | 0.1 | Per-pixel colour tolerance (0–1) |
| `DIFF_THRESHOLD` | 0.0005 | Max fraction of differing pixels (0.05%) |

`DIFF_THRESHOLD` is deliberately tight. Measured on this suite: a wrong workspace
profile changes one header label and moves 0.083%–0.213% of pixels. At the previous
1% budget that real regression passed on all seven views.

## Capture Contract

Three things make the frames reproducible; do not remove them.

1. **One fresh document per view.** The console is a single page keyed by URL hash, so
   navigating between views is a same-document hash change. The previous harness reused
   one page and produced seven byte-identical screenshots of a single view.
2. **Proven capture.** Each frame is rejected unless `.view.active` is the requested
   view, no `<dialog[open]>` covers it, and the view rendered text.
3. **Frozen inputs.** `page.clock.setFixedTime`, `timezoneId: UTC`, `locale: en-US`,
   `reducedMotion: reduce`, animation/transition/caret suppression, a seeded
   `dcc-workspace-profile-v1` record (so the onboarding modal does not open), and
   Chromium launch flags `--disable-gpu --disable-partial-raster
   --force-color-profile=srgb`. Without the raster flags a 1px border on a tile
   boundary painted 1–3 different pixels on some runs (observed on `economics.png`,
   x=270..271); with them, repeated captures are byte-identical.

## Coverage Limits

Six views (`economics`, `placement`, `forecast`, `security`, `ops`, `quality`) render
their "select a tenant UUID" state. Their modules fetch `/v1/*`
(e.g. `ui/economics-dashboard.js:154`), which the application served by
`scripts/run-local.py` does not expose — `/v1/costs` returns 404 while `/v2/costs`
exists. Until that mismatch is fixed, these baselines cover the console shell, the
view mounting and the layout, not populated tables or charts. Regenerate the baselines
after such a fix.

Baselines are environment-specific: fonts and rasterisation differ across platforms.
Generate them in the same image the gate runs in, or the first CI run will fail on
every view.

## Updating Baselines

```bash
node tests/iac-visual/iac_visual_regression.js --update-baseline
git add tests/iac-visual/baseline/
git commit -m "Update IaC visual baselines for <change>"
```

## CI Integration

```yaml
- name: Install browser
  run: npx playwright install --with-deps chromium

- name: Start application
  run: |
    PYTHONPATH=src DCC_DATABASE_URL="$DCC_DATABASE_URL" DCC_ALLOW_ANONYMOUS=1 \
      .venv/bin/python scripts/run-local.py --host 127.0.0.1 --port 8790 &
    # No sleep: the harness polls /healthz for up to 30s and fails loudly if it never answers.

- name: IaC & Compliance Visual Regression
  run: pytest tests/iac-visual/ -q
```
