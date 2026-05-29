# Quality Gates Checklist

Date: 2026-05-29

## Goal

- [x] Add a stable backend monitoring gate that does not depend on real market data, real MongoDB, Redis, Docker, or pytest.
- [x] Add a frontend type-check gate.
- [x] Add a frontend production build gate.
- [x] Add a Docker build gate for the frontend image.
- [x] Add a backend smoke gate that runs with the Python standard library only.
- [x] Keep the gate narrow enough to avoid existing historical tests that depend on external APIs or local services.

## Regression Coverage

- [x] Watchlist monitoring must preserve full scan coverage: 9 targets must produce 9 `scanned_items`.
- [x] `max_deep_analysis` must limit generated reports only, not scanned targets.
- [x] Scan results must distinguish `scanned_count`, `triggered_count`, `report_count`, `no_signal_count`, and `error_count`.
- [x] Missing-price quote sentinels such as `change_percent=-100` must not create false signals.
- [x] Valid current price plus previous close must recompute change percent instead of trusting a sentinel percentage.

## Commands

- [x] Backend script syntax: `python3 -m py_compile scripts/validation/monitoring_quality_gate.py`
- [x] Backend smoke: `python3 scripts/validation/monitoring_quality_gate.py`
- [x] Frontend dependency install: `yarn install --frozen-lockfile --production=false --network-timeout 300000`
- [x] Frontend type-check: `COREPACK_ENABLE_AUTO_PIN=0 yarn type-check`
- [x] Frontend production build: `COREPACK_ENABLE_AUTO_PIN=0 yarn vite build`
- [x] Frontend Docker build on Huawei Cloud server: `docker build --file Dockerfile.frontend --tag tradingagents-frontend:quality .`

## CI Workflow

- [x] Workflow file: `.github/workflows/quality-gates.yml`
- [x] Runs on `main` and `dev/custom-stock-agent` pushes.
- [x] Runs on pull requests targeting `main` or `dev/custom-stock-agent`.
- [x] Allows manual `workflow_dispatch`.
- [x] Does not require secrets.
- [x] Backend smoke job does not install project dependencies or touch external services.

## Residual Risks

- Full end-to-end browser tests are not included yet.
- API contract fuzzing with OpenAPI/Schemathesis is not included yet.
- Backend smoke uses deterministic mocks; it catches regressions in monitoring semantics but not live provider failures.
- Full backend Docker build is not part of this gate because the current Dockerfile downloads Pandoc from GitHub during build and is too heavy for a fast monitoring regression gate.
- Frontend build currently emits non-blocking Sass legacy JS API warnings and chunk-size warnings.
