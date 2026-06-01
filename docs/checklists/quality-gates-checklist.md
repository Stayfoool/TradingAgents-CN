# Quality Gates Checklist

Date: 2026-05-29

## Status Overview

| ID | Item | Status | Verification / Next Step |
| --- | --- | --- | --- |
| QG-1 | 统一质量入口 `scripts/validation/quality_verify.py` | Done | 已创建，支持 `precommit` / `backend` / `services` / `frontend` / `frontend-e2e` / `all`。 |
| QG-2 | 本地快捷命令 `Makefile` | Done | 已创建 `make verify-backend`、`make verify-frontend`、`make verify-e2e`。 |
| QG-3 | pre-commit 配置 | Done | `.pre-commit-config.yaml` 已创建，`.git/hooks/pre-commit` 已安装。 |
| QG-4 | Ruff 质量检查 | Partially Done | 已接入 backend profile 并通过；当前只覆盖质量门禁相关文件。 |
| QG-5 | 后端质量 pytest | Done | `tests/quality` 已通过：6 passed, 1 warning。 |
| QG-6 | 后端确定性 smoke gate | Done | `monitoring_quality_gate.py` 已通过，覆盖 9 个 watchlist 扫描与 `-100%` 哨兵值问题。 |
| QG-7 | Schemathesis API 合约 smoke | Done | 已包含在 `tests/quality/test_api_contract_quality.py`，随 backend profile 通过。 |
| QG-8 | GitHub Actions 统一调用 | Configured | `.github/workflows/quality-gates.yml` 已改为调用 `quality_verify.py`；待下一次 push 后确认远端结果。 |
| QG-9 | 前端 type-check / unit / build profile | Done | `python3 scripts/validation/quality_verify.py --profile frontend` 已通过；存在非阻塞 Sass 和 chunk-size 警告。 |
| QG-10 | Playwright E2E profile | Configured | `frontend-e2e` profile 已创建；本轮未重新运行浏览器测试。 |
| QG-11 | 扩展服务回归 profile | Configured | `services` profile 已创建；尚未运行验证。 |
| QG-12 | Testcontainers / Docker Compose 真实依赖测试 | Not Started | 后续为 MongoDB/Redis 集成测试补。 |
| QG-13 | 智能选股专项 harness | Not Started | 等智能选股代码开始后补 DSL golden tests、查询构造测试、文本事件防未来数据测试。 |
| QG-14 | LLM 专项评测 | Not Started | Langfuse / DeepEval / Ragas 后置。 |

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
- [x] Add a unified quality runner shared by local development, Huawei Cloud, and GitHub Actions.
- [x] Add a lightweight pre-commit entry for fast local checks.

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
- [x] Unified gate runner: `scripts/validation/quality_verify.py`
- [x] Pre-commit config: `.pre-commit-config.yaml`
- [x] Harness engineering runbook: `docs/quality/harness-engineering.md`
- [x] Makefile shortcuts: `Makefile`

## Commands Verified Locally

- [x] Backend script syntax: `python -m py_compile scripts/validation/monitoring_quality_gate.py`
- [x] Backend smoke: `python scripts/validation/monitoring_quality_gate.py`
- [x] Backend quality tests: `python -m pytest -q tests/quality`
- [x] Unified pre-commit gate without Ruff in current local env: `python3 scripts/validation/quality_verify.py --profile precommit --skip-ruff`
- [x] Unified backend gate via temporary uv quality env: `uv run --no-project --with-requirements requirements-quality.txt python scripts/validation/quality_verify.py --profile backend`
- [ ] Extended service gate: `python3 scripts/validation/quality_verify.py --profile services`
- [x] Frontend dependency install: `yarn install --frozen-lockfile --production=false --network-timeout 300000`
- [x] Frontend type-check: `COREPACK_ENABLE_AUTO_PIN=0 yarn type-check`
- [x] Frontend unit tests: `COREPACK_ENABLE_AUTO_PIN=0 yarn test:unit`
- [x] Frontend production build: `COREPACK_ENABLE_AUTO_PIN=0 yarn vite build`
- [x] Unified frontend gate: `python3 scripts/validation/quality_verify.py --profile frontend`
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
- [x] Backend job runs `quality_verify.py --profile backend`.
- [x] Frontend job runs `quality_verify.py --profile frontend`.
- [x] Playwright job installs Chromium from the official Playwright CDN via `yarn playwright install --with-deps chromium`.
- [x] Playwright job runs `quality_verify.py --profile frontend-e2e`.
- [x] Frontend Docker build waits for frontend build and E2E jobs.

## Residual Risks

- API contract coverage is a focused OpenAPI/Schemathesis smoke check, not full schema fuzzing against the whole production app.
- Backend monitoring tests stub DB, Redis, provider, and notification integrations; they catch monitoring semantics regressions but not live provider outages or credential failures.
- Full backend Docker build is not in this gate because the current backend Dockerfile downloads Pandoc and wkhtmltopdf during build, which makes the gate slower and more network-sensitive.
- Staging compose has been added as a pre-production path; actual server startup and health checks still need to be run on the Huawei Cloud host.
- Frontend build still emits non-blocking Sass legacy JS API warnings and chunk-size warnings.
- Ruff currently covers the quality gate runner, deterministic smoke script, and `tests/quality`; expanding it to all historical Python code should be gradual.
- Current local machine does not have the full quality dependency set installed globally; the backend profile was verified through a temporary `uv` quality environment.
