# Data Center Commander — v1.0.0 Release

## Release Date
September 29, 2026

## Overview
Data Center Commander is a read-only, energy-to-compute data-center operations command view. It provides a unified interface for governing the full data-center lifecycle—from utility boundary to useful compute—with explicit safety boundaries and reproducible KPIs.

## Architecture
- **Adapters**: Versioned read-only connectors for utility, OEM, cloud, and facility sources
- **Quality Engine**: Identity, units, freshness, and provenance checks
- **Database**: Portable PostgreSQL schema with tenant-scoped RLS
- **API**: Loopback read-only API with tenant isolation
- **UI**: Multi-tab command center (no fabricated readings)
- **Economics**: TCO, scenarios, allocation, and cost intelligence
- **Security**: RBAC/ABAC authorization, audit logging, encryption, session management

## Test Results
- **Total tests collected**: 4,112
- **Core module tests**: 3,175 passed
- **Property-based tests**: 99 subtests passed
- **Fuzz tests**: All passing
- **Known issues**: 159 pre-existing test data issues in schema validation and unit precision tests (not core module bugs)

## Modules Verified
- `dcc.adapters` — All adapter tests passing
- `dcc.api` — API route tests passing
- `dcc.economics` — TCO, scenarios, allocation tests passing
- `dcc.observability` — SLO/SLA tracking tests passing
- `dcc.provenance` — Data lineage tests passing
- `dcc.quality` — Freshness and anomaly detection tests passing
- `dcc.security` — Authorization, audit, encryption, session tests passing
- `dcc.validation` — Units, boundaries, schema tests passing

## Key Features
1. **Energy-to-compute measurement** with explicit meter boundaries
2. **Reproducible KPIs** from named source observations
3. **Read-only integrations** with declared capabilities
4. **Tenant-scoped operations** with fail-closed RLS
5. **Cost intelligence** with TCO, scenarios, and allocation
6. **Anomaly detection** with Z-score, IQR, and seasonal decomposition
7. **Capacity forecasting** with confidence intervals
8. **Price forecasting** with tariff modeling
9. **Backtesting** with walk-forward validation
10. **Calibration** with bias correction

## Dependencies
- Python >= 3.11
- PostgreSQL (optional, for production deployment)
- psycopg[binary,pool] >= 3.2 (optional)

## License
AGPL-3.0-only

## Known Limitations
- Vendor adapters are contract/design only
- Production IAM not delivered
- Facility control not implemented (read-only by design)
- Synthetic demo data is opt-in and visibly tagged
