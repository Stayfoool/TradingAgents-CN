# Smart Stock Screening Checklist

Date: 2026-06-01

## Status Overview

| ID | Phase | Item | Status | Verification / Next Step |
| --- | --- | --- | --- | --- |
| SS-1 | Planning | 方案文档 | Done | `docs/implementation/smart-stock-screening-plan.md` 已创建。 |
| SS-2 | Planning | 执行清单 | Done | 当前 checklist 已创建。 |
| SS-3 | Phase 1: Backend Core | DSL schema | Done | `app/services/smart_screening/schema.py` 已定义 Pydantic DSL，覆盖 universe、conditions、sort、limit、as_of。 |
| SS-4 | Phase 1: Backend Core | 字段/指标注册表 | Done | `app/services/smart_screening/registry.py` 已定义字段来源、类型、可用操作符、执行模式。 |
| SS-5 | Phase 1: Backend Core | DSL validator | Done | `app/services/smart_screening/validator.py` 已校验字段、操作符、日期窗口、排序和文本事件未来数据。 |
| SS-6 | Phase 1: Backend Core | Execution planner | Done | `app/services/smart_screening/planner.py` 输出执行模式、字段、集合和步骤。 |
| SS-7 | Phase 1: Backend Core | `run_stock_screening_by_dsl` | Done | `app/services/smart_screening/service.py` 受控执行 DSL 并返回候选股、理由和证据。 |
| SS-8 | Phase 1: Backend Core | 固定样例数据 | Done | `app/services/smart_screening/sample_data.py` 覆盖行情、财务、文本事件和未来数据样例。 |
| SS-9 | Phase 5: Quality Gates | DSL golden tests | Done | `tests/quality/test_api_contract_quality.py` 覆盖自然语言到 DSL/API 的固定样例。 |
| SS-10 | Phase 5: Quality Gates | Mongo 查询构造测试 | Done | `tests/quality/test_smart_screening_execution_quality.py` 校验 market/date/universe 查询构造。 |
| SS-11 | Phase 5: Quality Gates | 文本事件防未来数据测试 | Done | `as_of=2026-05-31` 时 2026-06-02 样例新闻不会被使用。 |
| SS-12 | Phase 3: API And Frontend | 后端 API | Done | `app/routers/smart_screening.py` 新增 parse/plan/run/run-natural-language 接口。 |
| SS-13 | Phase 3: API And Frontend | 前端页面/入口 | Done | `frontend/src/views/Screening/index.vue` 增加智能选股入口、DSL、候选股、理由和证据展示。 |
| SS-14 | Phase 4: Agent Integration | 现有 analysts 深度分析接入 | Done | `build_deep_analysis_tasks()` 将 Top N 候选股转换为 market/fundamentals/news analyst 任务上下文。 |
| SS-15 | Phase 4: Agent Integration | Audit / evidence check | Done | `audit_screening_result()` 校验候选股证据可追溯性。 |
| SS-16 | Phase 5: Quality Gates | Playwright 流程测试 | Done | `frontend/e2e/smart-screening.spec.ts` 覆盖智能选股页面流程。 |
| SS-17 | Phase 5: Quality Gates | CI 接入 | Done | 智能选股测试纳入既有 `tests/quality` 与 `frontend/e2e` 门禁路径。 |

## Phase 1: Backend Core

- [x] SS-3 定义 DSL Pydantic schema。
- [x] SS-4 定义字段/指标注册表。
- [x] SS-5 实现 DSL validator。
- [x] SS-6 实现 execution planner。
- [x] SS-7 实现 `run_stock_screening_by_dsl(dsl)` 最小版本。
- [x] SS-8 增加固定样例数据 fixture。
- [x] 增加 DSL 和执行计划测试。

## Phase 2: Data Integration

- [x] 确认 `stock_daily_quotes` 字段映射。
- [x] 确认 `stock_financial_data` 字段映射。
- [x] 设计 `stock_daily_factors` 首批字段。
- [x] 设计 `stock_text_events` 首批字段。
- [x] 支持从历史行情动态计算收益、均线、量价指标。
- [x] 支持文本事件按时间、来源、事件类型、关键词查询。

## Phase 3: API And Frontend

- [x] SS-12 新增智能选股后端 API。
- [x] SS-13 新增自然语言输入入口。
- [x] SS-13 展示 DSL 预览。
- [x] SS-13 展示候选股列表。
- [x] SS-13 展示命中原因和证据。
- [x] SS-13 展示数据缺口和不确定性。

## Phase 4: Agent Integration

- [x] 接入可选 LLM 生成 DSL，默认规则解析回退。
- [x] SS-14 对 Top N 候选股生成现有 market analyst 深度分析任务上下文。
- [x] SS-14 对 Top N 候选股生成现有 fundamentals analyst 深度分析任务上下文。
- [x] SS-14 对 Top N 候选股生成现有 news analyst 深度分析任务上下文。
- [x] 增加综合总结 agent。
- [x] SS-15 增加规则化审计校验；LLM 审计 agent 后续再接。

## Phase 5: Quality Gates

- [x] DSL schema / registry / validator quality tests。
- [x] SS-9 DSL golden tests。
- [x] SS-10 Mongo 查询构造测试。
- [x] 固定样例数据筛选测试。
- [x] SS-11 文本事件防未来数据测试。
- [x] API contract smoke。
- [x] SS-16 Playwright 关键流程测试。
- [x] SS-17 接入 `quality_verify.py`。

## Current Decision Log

- [x] 第一阶段只聚焦 TuShare + AKShare。
- [x] 暂不引入 iFinD / Choice / Wind 订阅依赖。
- [x] LLM 只生成 DSL 和解释结果，不直接查库。
- [x] Python 工具负责校验 DSL、查询数据、动态计算和返回证据。
- [x] 第一版保留 `stock_daily_factors` 和 `stock_text_events`。
- [x] 第一版不做 `stock_factor_latest` 和 `stock_text_signals_latest`。
- [x] 现有 analysts 只用于候选股 Top N 深度分析，不用于全市场逐只扫描。

## Verification Log

- [x] `UV_CACHE_DIR=/private/tmp/tradingagents-uv-cache uv run --no-project --with-requirements requirements-quality.txt python -m pytest -q tests/quality/test_smart_screening_dsl_quality.py` -> `7 passed`
- [x] `UV_CACHE_DIR=/private/tmp/tradingagents-uv-cache uv run --no-project --with-requirements requirements-quality.txt python scripts/validation/quality_verify.py --profile backend` -> `13 passed, 1 warning`
- [x] `UV_CACHE_DIR=/private/tmp/tradingagents-uv-cache uv run --no-project --with-requirements requirements-quality.txt python -m pytest -q tests/quality/test_api_contract_quality.py tests/quality/test_smart_screening_execution_quality.py tests/quality/test_smart_screening_dsl_quality.py` -> `15 passed, 4 warnings`
- [x] `UV_CACHE_DIR=/private/tmp/tradingagents-uv-cache uv run --no-project --with-requirements requirements-quality.txt python -m pytest -q tests/quality/test_smart_screening_execution_quality.py` -> `6 passed`
- [x] `yarn type-check` -> passed
- [x] `COREPACK_ENABLE_AUTO_PIN=0 yarn playwright test e2e/smart-screening.spec.ts --workers=1` -> `1 passed`
- [x] `UV_CACHE_DIR=/private/tmp/tradingagents-uv-cache uv run --no-project --with-requirements requirements-quality.txt python -m pytest -q tests/quality/test_smart_screening_execution_quality.py tests/quality/test_api_contract_quality.py` -> `14 passed, 4 warnings`
- [x] `UV_CACHE_DIR=/private/tmp/tradingagents-uv-cache uv run --no-project --with-requirements requirements-quality.txt python scripts/validation/quality_verify.py --profile backend` -> `20 passed, 4 warnings`
- [x] `COREPACK_ENABLE_AUTO_PIN=0 python3 scripts/validation/quality_verify.py --profile frontend` -> type-check passed, unit `12 passed`, build passed
- [x] `COREPACK_ENABLE_AUTO_PIN=0 python3 scripts/validation/quality_verify.py --profile frontend-e2e` -> `2 passed`
