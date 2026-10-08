# CHANGELOG.md

## [4.0.0] — Nvidia Technology Integration

### Added
- Nvidia Clara threat intel enrichment (optional API integration)
- Nvidia Morpheus pipeline integration (optional, real-time SOC analytics)
- Nvidia RAPIDS/cuML GPU acceleration pathways (optional)
- GPU-accelerated correlation benchmark (CPU vs GPU comparison)
- 3 new CLI commands: `dcc clara`, `dcc gpu`, `dcc benchmark`
- `improvements/` directory with test suites and examples
- `dcc/api/stubs.pyi` — Type stubs for IDE support
- `improvements/dcc_examples.py` — Usage examples for all 5 functions
- `improvements/test_dcc_api.py` — Comprehensive test suite (30+ tests)
- `improvements/test_imports.py` — Import verification and docstring checks
- `improvements/dcc_cli.py` — CLI entry point for DCC API functions

### Fixed
- `src/dcc/dcc_api.py` — Ruff lint errors resolved (UP006, SIM105, SIM108, W292)
- `src/dcc/dcc_api.py` — Mypy type annotation standardization (3 `# type: ignore` entries)
- `src/dcc/dcc_api.py` — `try-except-pass` replaced with `contextlib.suppress(Exception)` in 3 functions
- Type annotations upgraded from `Dict` to `list` for Python 3.9 compatibility
- All functions verified importable and functional with zero Nvidia API calls

### Changed
- Return type annotations standardized across all 5 SOC functions
- Nerve context governance uses `contextlib.suppress(Exception)` pattern
- Optional Nvidia technology integrations (Clara, Morpheus, RAPIDS)
- CLI enhanced with new commands for GPU/Clara benchmarking

### Deprecated
- None

### Removed
- None

## [3.1.1] — Bug Fixes

### Fixed
- `connector_traffic` return type annotation consistency
- `wazuh_rules` filter parameter handling
- Dashboard metrics empty result handling

### Changed
- Minor docstring improvements
- Dependency version bumps

## [3.1.0] — Nvidia Integration Preview

### Added
- Preliminary Nvidia technology integration points
- Optional API keys for Clara enrichment
- GPU acceleration flag parameters
- Benchmark generation scripts

### Changed
- Updated dependency requirements
- Improved error handling for network failures

## [3.0.0] — Initial Nvidia-Ready Release

### Added
- Initial 5 SOC function wrapper release
- AGPL-3.0 license with ISO 42001 governance chassis
- Zero Nvidia API calls between sessions (40 RPM compliance)
- Docker + k8s free-tier compatible
- Broker channel distribution support