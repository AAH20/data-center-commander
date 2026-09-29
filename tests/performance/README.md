# Data Center Commander — Performance Test Suite

Comprehensive performance testing for the Data Center Commander API using **k6** and **Artillery**.

## Test Types

| Test | Purpose | k6 | Artillery |
|------|---------|----|-----------|
| **Load** | Normal production traffic patterns | `k6/load-test.js` | `artillery/load-test.yml` |
| **Stress** | Beyond capacity to find breaking points | `k6/stress-test.js` | `artillery/stress-test.yml` |
| **Spike** | Sudden traffic surges | `k6/spike-test.js` | `artillery/spike-test.yml` |
| **Endurance** | Sustained load for leak detection | `k6/endurance-test.js` | `artillery/endurance-test.yml` |

## Prerequisites

### k6
```bash
brew install k6
```

### Artillery
```bash
npm install -g artillery
# or locally:
cd tests/performance && npm install
```

## Quick Start

### Run all k6 tests
```bash
cd tests/performance
npm run test:k6:all
```

### Run all Artillery tests
```bash
cd tests/performance
npm run test:artillery:all
```

### Run individual tests

#### k6
```bash
# Load test
k6 run k6/load-test.js

# Stress test
k6 run k6/stress-test.js

# Spike test
k6 run k6/spike-test.js

# Endurance test (default 15m, configurable)
k6 run --env DURATION=30m --env VUS=50 k6/endurance-test.js
```

#### Artillery
```bash
# Load test
npx artillery run artillery/load-test.yml

# Stress test
npx artillery run artillery/stress-test.yml

# Spike test
npx artillery run artillery/spike-test.yml

# Endurance test
DURATION=30 npx artillery run artillery/endurance-test.yml
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `http://127.0.0.1:8790` | API base URL |
| `TENANT_ID` | `00000000-0000-4000-8000-000000000001` | Tenant UUID for requests |
| `DURATION` | `15m` (k6) / `900` (Artillery) | Endurance test duration |
| `VUS` | `25` | Virtual users for endurance test |

### Example with custom config
```bash
k6 run --env BASE_URL=http://api.example.com --env TENANT_ID=your-uuid k6/load-test.js
```

## Test Scenarios

### Load Test
- **k6**: 10→20 VUs over 9 minutes, tests core endpoints
- **Artillery**: 5→20 arrival rate, 4 weighted scenarios (Dashboard, Assets, Operations, Costs)

### Stress Test
- **k6**: Ramps to 200 VUs, tests heavy endpoints (analytics, costs, capacity)
- **Artillery**: Ramps to 200 arrival rate, focuses on expensive queries

### Spike Test
- **k6**: Sudden jumps 5→100→5→150 VUs, simulates dashboard refresh storms
- **Artillery**: Rapid spikes with recovery periods, tests monitoring agent patterns

### Endurance Test
- **k6**: Sustained 25 VUs for 15+ minutes, all endpoints
- **Artillery**: Sustained 25 arrival rate, full dashboard cycles

## Thresholds

### k6 Thresholds
- **Load**: p95 < 1500ms, p99 < 3000ms, error rate < 5%
- **Stress**: p95 < 3000ms, p99 < 5000ms, error rate < 10%
- **Spike**: p95 < 2000ms, p99 < 4000ms, error rate < 8%
- **Endurance**: p95 < 2000ms, p99 < 4000ms, error rate < 5%

### Artillery Thresholds
- Similar thresholds via `ensure` config in YAML files

## Output

### k6
- Console output with VU counts, request rates, latency percentiles
- Exit code 1 if thresholds fail

### Artillery
- HTML report in `tests/performance/artillery/report/`
- JSON metrics available via `--output` flag

## CI Integration

### GitHub Actions
```yaml
- name: Run k6 load test
  uses: grafana/k6-action@v0.3.1
  with:
    filename: tests/performance/k6/load-test.js

- name: Run Artillery tests
  run: |
    npm install -g artillery
    artillery run tests/performance/artillery/load-test.yml
```

## Endpoints Tested

- `GET /healthz` — Health check
- `GET /readyz` — Readiness probe
- `GET /v1/overview` — Dashboard overview
- `GET /v1/assets` — Asset inventory
- `GET /v1/facilities` — Facility list
- `GET /v1/workflows` — Operational workflows
- `GET /v1/analytics` — KPI analytics (configurable window)
- `GET /v1/topology` — Asset topology graph
- `GET /v1/costs` — Cost estimates and actuals
- `GET /v1/capacity` — Capacity snapshots
- `GET /v1/evidence` — Evidence events
- `GET /v1/connectors` — Connector status

## Notes

- Tests require a running DCC instance with database configured
- Default tenant ID is a placeholder — replace with valid UUID for your environment
- Artillery tests use `processor: "./artillery/helpers.js"` for custom metrics
- k6 tests use shared utilities in `k6/shared.js`
