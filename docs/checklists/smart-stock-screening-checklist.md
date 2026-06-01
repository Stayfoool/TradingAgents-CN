# Smart Stock Screening Checklist

Date: 2026-06-01

## Status Overview

| ID | Item | Status | Verification / Next Step |
| --- | --- | --- | --- |
| SS-1 | 方案文档 | Done | `docs/implementation/smart-stock-screening-plan.md` 已创建。 |
| SS-2 | 执行清单 | Done | 当前 checklist 已创建。 |
| SS-3 | DSL schema | Done | `app/services/smart_screening/schema.py` 已定义 Pydantic DSL，覆盖 universe、conditions、sort、limit、as_of。 |
| SS-4 | 字段/指标注册表 | Done | `app/services/smart_screening/registry.py` 已定义字段来源、类型、可用操作符、执行模式。 |
| SS-5 | DSL validator | Done | `app/services/smart_screening/validator.py` 已校验字段、操作符、日期窗口、排序和文本事件未来数据。 |
| SS-6 | Execution planner | Not Started | 输出 `historical_factor` / `dynamic_price_calc` / `text_event_search` 等执行模式。 |
| SS-7 | `run_stock_screening_by_dsl` | Not Started | 受控 Python 工具，接收 DSL 并返回候选股和证据。 |
| SS-8 | 固定样例数据 | Not Started | 构造小型行情、财务、文本事件样例，避免依赖外部 API。 |
| SS-9 | DSL golden tests | Not Started | 固定自然语言样例和期望 DSL。 |
| SS-10 | Mongo 查询构造测试 | Not Started | 验证 query / aggregation 不漏条件、不误用字段。 |
| SS-11 | 文本事件防未来数据测试 | Not Started | 指定 `as_of` 时禁止引用未来新闻、公告、研报。 |
| SS-12 | 后端 API | Not Started | 新增智能选股解析、执行、结果接口。 |
| SS-13 | 前端页面/入口 | Not Started | 输入自然语言，展示 DSL、候选股、命中原因、证据。 |
| SS-14 | 现有 analysts 深度分析接入 | Not Started | 只对 Top N 候选股调用 market / fundamentals / news analyst。 |
| SS-15 | Audit / evidence check | Not Started | 校验输出是否能追溯到数据库字段或文本事件。 |
| SS-16 | Playwright 流程测试 | Not Started | 覆盖输入自然语言、执行筛选、查看候选股和证据。 |
| SS-17 | CI 接入 | Not Started | 将智能选股关键测试加入质量门禁。 |

## Phase 1: Backend Core

- [x] 定义 DSL Pydantic schema。
- [x] 定义字段/指标注册表。
- [x] 实现 DSL validator。
- [ ] 实现 execution planner。
- [ ] 实现 `run_stock_screening_by_dsl(dsl)` 最小版本。
- [ ] 增加固定样例数据 fixture。
- [ ] 增加 DSL 和执行计划测试。

## Phase 2: Data Integration

- [ ] 确认 `stock_daily_quotes` 字段映射。
- [ ] 确认 `stock_financial_data` 字段映射。
- [ ] 设计 `stock_daily_factors` 首批字段。
- [ ] 设计 `stock_text_events` 首批字段。
- [ ] 支持从历史行情动态计算收益、均线、量价指标。
- [ ] 支持文本事件按时间、来源、事件类型、关键词查询。

## Phase 3: API And Frontend

- [ ] 新增智能选股后端 API。
- [ ] 新增自然语言输入入口。
- [ ] 展示 DSL 预览。
- [ ] 展示候选股列表。
- [ ] 展示命中原因和证据。
- [ ] 展示数据缺口和不确定性。

## Phase 4: Agent Integration

- [ ] 接入 LLM 生成 DSL。
- [ ] 对 Top N 候选股调用现有 market analyst。
- [ ] 对 Top N 候选股调用现有 fundamentals analyst。
- [ ] 对 Top N 候选股调用现有 news analyst。
- [ ] 增加综合总结 agent。
- [ ] 增加审计校验 agent。

## Phase 5: Quality Gates

- [x] DSL schema / registry / validator quality tests。
- [ ] DSL golden tests。
- [ ] Mongo 查询构造测试。
- [ ] 固定样例数据筛选测试。
- [ ] 文本事件防未来数据测试。
- [ ] API contract smoke。
- [ ] Playwright 关键流程测试。
- [ ] 接入 `quality_verify.py`。

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
