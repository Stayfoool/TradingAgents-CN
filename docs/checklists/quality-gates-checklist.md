# Quality Gates Checklist

Date: 2026-05-29

## Goal

- [x] Add a backend pytest gate for watchlist monitoring regressions.
- [x] Add a backend pytest-asyncio gate for async monitoring service behavior.
- [x] Add a deterministic backend smoke gate that does not require real market data, MongoDB, Redis, Docker, or API keys.
- [x] Add an API contract smoke gate based on a FastAPI OpenAPI schema and Schemathesis loader.
- [x] Add frontend unit tests with Vitest and Vue Test Utils.
- [x] Add a Playwright browser test for the login and monitoring scan flow.
- [x] Add frontend type-check, production build, and frontend Docker build gates.
- [x] Add a staging compose override for pre-production validation.
- [x] Keep gates narrow enough to avoid historical tests that depend on external APIs or local services.

## Regression Coverage

- [x] Watchlist monitoring must preserve full scan coverage: 9 targets must produce 9 `scanned_items`.
- [x] `max_deep_analysis` must limit generated reports only, not scanned targets.
- [x] Scan results must distinguish `scanned_count`, `triggered_count`, `report_count`, `no_signal_count`, and `error_count`.
- [x] Missing-price quote sentinels such as `change_percent=-100` must not create false signals.
- [x] Valid current price plus previous close must recompute change percent instead of trusting a sentinel percentage.
- [x] Monitoring UI must display a run summary with 9 scanned, 1 triggered, and 8 no-signal items.
- [x] Browser flow must cover login, entering `/monitoring`, clicking scan, and seeing the expected completion message.
- [x] Minimal API schema must expose `/api/watchlists`, `/api/portfolio/positions`, `/api/monitoring/watchlist/run`, `/api/monitoring/reports`, and `/api/monitoring/runs`.

## Files

- [x] Backend quality tests: `tests/quality/test_monitoring_quality.py`
- [x] API contract smoke tests: `tests/quality/test_api_contract_quality.py`
- [x] Frontend unit test: `frontend/src/views/Monitoring/__tests__/monitoring-summary.spec.ts`
- [x] Vitest setup: `frontend/src/test/setup.ts`
- [x] Playwright config: `frontend/playwright.config.ts`
- [x] Playwright monitoring flow: `frontend/e2e/monitoring.spec.ts`
- [x] CI workflow: `.github/workflows/quality-gates.yml`
- [x] Quality dependency set: `requirements-quality.txt`
- [x] Staging compose override: `docker-compose.staging.yml`
- [x] Staging runbook: `docs/quality/staging.md`

## Commands Verified Locally

- [x] Backend script syntax: `python -m py_compile scripts/validation/monitoring_quality_gate.py`
- [x] Backend smoke: `python scripts/validation/monitoring_quality_gate.py`
- [x] Backend quality tests: `python -m pytest -q tests/quality`
- [x] Frontend dependency install: `yarn install --frozen-lockfile --production=false --network-timeout 300000`
- [x] Frontend type-check: `COREPACK_ENABLE_AUTO_PIN=0 yarn type-check`
- [x] Frontend unit tests: `COREPACK_ENABLE_AUTO_PIN=0 yarn test:unit`
- [x] Frontend production build: `COREPACK_ENABLE_AUTO_PIN=0 yarn vite build`
- [x] Frontend Playwright E2E: `COREPACK_ENABLE_AUTO_PIN=0 yarn test:e2e`
- [ ] Frontend Docker build in GitHub Actions after push.
- [ ] Staging stack startup on Huawei Cloud server.

## CI Workflow

- [x] Workflow file: `.github/workflows/quality-gates.yml`
- [x] Runs on `main` and `dev/custom-stock-agent` pushes.
- [x] Runs on pull requests targeting `main` or `dev/custom-stock-agent`.
- [x] Allows manual `workflow_dispatch`.
- [x] Does not require secrets.
- [x] Backend job installs only `requirements-quality.txt`.
- [x] Backend job runs script compile, deterministic smoke, and `pytest -q tests/quality`.
- [x] Frontend job runs type-check, Vitest, and Vite build.
- [x] Playwright job installs Chromium from the official Playwright CDN via `yarn playwright install --with-deps chromium`.
- [x] Frontend Docker build waits for frontend build and E2E jobs.

## Residual Risks

- API contract coverage is a focused OpenAPI/Schemathesis smoke check, not full schema fuzzing against the whole production app.
- Backend monitoring tests stub DB, Redis, provider, and notification integrations; they catch monitoring semantics regressions but not live provider outages or credential failures.
- Full backend Docker build is not in this gate because the current backend Dockerfile downloads Pandoc and wkhtmltopdf during build, which makes the gate slower and more network-sensitive.
- Staging compose has been added as a pre-production path; actual server startup and health checks still need to be run on the Huawei Cloud host.
- Frontend build still emits non-blocking Sass legacy JS API warnings and chunk-size warnings.
