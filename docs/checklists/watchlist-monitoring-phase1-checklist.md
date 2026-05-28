# Watchlist Monitoring Phase 1 Checklist

Date: 2026-05-28

## User Requirements

- [x] Support proactive monitoring while the server is running.
- [x] If resources are limited, support at least one daily scan.
- [x] Start with watchlist if full-market monitoring is too expensive.
- [x] Include buy-side and sell-side recommendations.
- [x] Include price movement, fundamentals, industry, announcements, and media/news evidence.
- [x] Trigger reasons must include authoritative media reports where available.
- [x] Preserve source attribution for facts such as revenue surprise and guidance.

## Local Project Capabilities Checked

- [x] Scheduler exists: `app/main.py`, `app/services/scheduler_service.py`, `app/routers/scheduler.py`.
- [x] Notifications exist: `app/services/notifications_service.py`, `app/models/notification.py`, `app/routers/notifications.py`.
- [x] Screening exists: `app/routers/screening.py`, `app/services/enhanced_screening_service.py`.
- [x] News storage/query exists: `app/services/news_data_service.py`, `app/routers/news_data.py`.
- [x] Quote ingestion exists: `app/services/quotes_ingestion_service.py`.
- [x] Analysis reports exist through existing analysis services and `analysis_reports`.

## External Source Rules

- [x] Prefer official provider documentation for APIs.
- [x] Treat unofficial scraping of news sites as out of scope for phase 1.
- [x] Record source URL and provenance for every factual media claim.

## External Sources Checked

- [x] Alpha Vantage documentation URL recorded.
- [x] Benzinga News API documentation URL recorded.
- [x] Finnhub Company News documentation URL recorded.
- [x] Finnhub Earnings Calendar documentation URL recorded.
- [ ] API keys and actual response formats verified in the deployed environment.
- [ ] Zacks official API availability verified. Do not implement Zacks scraping until this is resolved.

## Planned Implementation Items

- [x] Add watchlist CRUD.
- [x] Add portfolio/position CRUD.
- [x] Add monitoring run service.
- [x] Add signal rule engine.
- [x] Add evidence collector with authoritative-media scoring.
- [x] Add report builder with source-cited facts.
- [x] Register daily scheduler job.
- [x] Add notification creation for high-priority signals.
- [ ] Add minimal UI for watchlist and monitoring reports.

## Acceptance Criteria

- [x] Manual watchlist scan works in deployed backend.
- [x] Daily scheduled scan is registered in the deployed backend.
- [ ] Daily scheduled scan is visible in scheduler UI.
- [ ] Reports include price/volume/trend evidence.
- [x] Reports include authoritative media evidence or explicit not-found status.
- [x] Quote/K-line provider failure does not abort the whole ticker; reports can record explicit data gaps.
- [x] Authoritative media/fundamental evidence can trigger a report even when live quote data is temporarily unavailable.
- [x] Reports include buy/hold/sell/risk recommendation depending on watchlist or held position.
- [x] No factual claim from an LLM is accepted without evidence metadata.
- [x] Duplicate notifications for the same ticker/signal/day are suppressed by `monitoring_signals` upsert result.

## Deployed Verification

- [x] Backend rebuilt on Huawei Cloud from commit `2cd5a02` with `docker compose -f docker-compose.hub.nginx.yml -f docker-compose.localbuild.yml -f docker-compose.security.yml up -d --build backend`.
- [x] Backend health check passed with `curl -fsS http://127.0.0.1/api/health`, returning `status=ok`, `version=0.1.16`.
- [x] Scheduler startup log contains `Watchlist 自动监控已配置: 每日 16:30` and `Added job "Watchlist 自动监控（每日）"`.
- [x] SNOW smoke run with a temporary watchlist item and Benzinga-attributed evidence returned `target_count=1`, `report_count=1`, `error_count=0`.
- [x] SNOW smoke report stored `signal_type=buy_watch`, `severity=warning`, `evidence_count=1`, `signal_count=1`, `notification_count=1`.
- [x] SNOW smoke report recorded the live quote data gap: `行情数据获取失败：无法获取美股SNOW的行情数据：所有数据源均失败`.
- [x] Duplicate smoke run created two report records for audit history but kept `signal_count=1` and `notification_count=1`.
- [x] Temporary smoke test watchlist, monitoring, notification, and `codex_smoke` news data were removed after verification.

## Residual Risks

- News provider API quality, cost, and delay are not yet tested.
- US equities need a reliable quote/fundamental source configured before strong price/trend monitoring. Current server status: Yahoo/yfinance is rate-limited or DNS-failing, Alpha Vantage API key is not configured, and the configured Finnhub key returns 401 invalid key.
- A-share announcement and media evidence need separate weighting from US equities.
- Local `pytest` was unavailable through system Python, and `uv run` failed because the upstream optional `qianfan` dependency is unsatisfiable for one supported Python split. Pure-function checks and compile checks were run locally.
