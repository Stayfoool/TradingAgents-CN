# Watchlist 自动监控第一阶段方案

日期：2026-05-28

## 目标

第一阶段先做 watchlist 级别的自动监控，不做全市场实时 AI 分析。

系统在服务器开机运行时，至少每天自动检查一次 watchlist 和持仓列表，发现价格、成交量、趋势、财报、公告、新闻或权威媒体报道触发的机会/风险后，生成可追溯的分析摘要、买入/卖出/观察建议，并通过站内通知提醒用户。

## 第一阶段范围

包含：

- Watchlist：用户维护关注股票列表。
- Portfolio：用户维护已持仓股票列表，用于生成卖出、减仓、止损、继续持有建议。
- 每日自动扫描：默认按市场收盘后运行一次。
- 手动触发扫描：复用现有调度器手动触发能力。
- 异动检测：用规则先筛出候选股票，避免每只股票都调用大模型。
- 权威媒体证据：触发原因必须包含可追溯媒体报道或明确说明“未找到权威媒体证据”。
- 分析报告：对候选股票生成结构化摘要和建议。
- 通知提醒：重要机会或风险写入现有通知中心。

暂不包含：

- 自动交易下单。
- 全市场逐票深度分析。
- 高频秒级监控。
- 复杂组合优化。
- 自动调仓执行。

## 推荐技术路线

复用现有模块：

- 调度：`app/main.py` 中已有 APScheduler，`app/services/scheduler_service.py` 已有任务列表、暂停、恢复、手动触发、历史记录。
- 行情：`market_quotes`、`QuotesIngestionService`、`QuotesService` 已有 A 股行情入库和快照能力。
- 筛选：`app/services/enhanced_screening_service.py` 已有筛选服务。
- 新闻：`stock_news`、`NewsDataService`、`news_data_sync_service` 已有新闻入库和查询能力。
- 分析：`simple_analysis_service` 和 `analysis_reports` 已有单股分析与报告保存能力。
- 通知：`notifications_service` 已有站内通知和 WebSocket 推送。

新增模块建议：

- `app/models/watchlist.py`
- `app/routers/watchlist.py`
- `app/services/watchlist_service.py`
- `app/services/monitoring/watchlist_monitor_service.py`
- `app/services/monitoring/signal_rules.py`
- `app/services/monitoring/evidence_collector.py`
- `app/services/monitoring/report_builder.py`

新增集合建议：

- `watchlists`
- `portfolio_positions`
- `monitoring_runs`
- `monitoring_signals`
- `monitoring_evidence`
- `monitoring_reports`

## 数据源策略

行情和基本面：

- A 股：先复用 AKShare / TuShare / MongoDB 缓存。
- 美股：第一阶段优先接入 Alpha Vantage 或 Finnhub；如果没有 key，则先支持手动维护 watchlist，但美股自动证据会降级。

新闻和权威媒体：

- Alpha Vantage `NEWS_SENTIMENT` 可返回实时和历史市场新闻与情绪数据，覆盖股票、加密、外汇及并购、IPO、财政政策等主题，适合作为第一阶段新闻聚合来源。
- Benzinga Newsfeed API 官方支持按 ticker、主题、日期范围、更新时间、内容类型和重要性过滤，适合作为更高质量的美股新闻源。
- Finnhub Company News 可作为美股公司新闻来源；若当前页面抓取不到完整文档，实施前需要在本地验证 API 响应格式。
- Zacks 这类媒体如无正式 API，不在第一阶段做非授权抓取；只通过可合法获取的数据源返回的 URL/标题/摘要引用它。

权威媒体白名单第一版：

- Benzinga
- Zacks
- Reuters
- AP
- Bloomberg
- CNBC
- MarketWatch
- WSJ
- Barron's
- The Motley Fool
- Seeking Alpha
- PR Newswire
- Business Wire
- GlobeNewswire
- SEC company filing / EDGAR

说明：白名单用于证据加权，不代表这些来源都已接入。第一阶段必须记录每条证据的来源、标题、发布时间、URL、抓取来源和摘要。

## 触发规则

每次扫描分成两步：先规则筛选，再 AI 总结。

价格和成交量触发：

- 单日涨跌幅绝对值超过阈值，例如 `>= 5%`。
- 成交量超过 20 日均量，例如 `>= 2x`。
- 价格突破 20/60 日高点。
- 价格跌破 20/60 日均线或关键支撑。
- 连续上涨或连续下跌，例如 5 个交易日内至少 4 日同向。
- 从低点反弹，例如过去 60 日低点以来反弹超过 `15%`。

基本面和事件触发：

- 财报日或财报后 2 个交易日。
- 营收、EPS、利润率、现金流或指引明显高于/低于预期。
- 公司公告、SEC filing、A 股公告出现重大事项。
- 分析师评级/目标价大幅调整。
- 行业同类股票同步异动。

新闻和权威媒体触发：

- 白名单媒体出现与该股票相关的高重要性报道。
- 新闻标题/摘要包含关键词：earnings beat、guidance raise、revenue growth、margin expansion、downgrade、lawsuit、SEC investigation、guidance cut、misses estimates、layoffs 等。
- 新闻发布时间与价格异动时间窗口匹配，例如前后 48 小时。

## 信号类型

第一阶段输出四类信号：

- `buy_watch`：潜在买入观察。
- `hold_confirm`：持仓继续持有确认。
- `sell_watch`：潜在卖出/减仓观察。
- `risk_alert`：风险警报。

不直接输出“必须买入/必须卖出”，而是输出建议和证据，保留人工判断。

## 证据结构

每个触发原因必须结构化保存：

```json
{
  "type": "authoritative_media",
  "source": "Benzinga",
  "title": "Snowflake stock surges after earnings beat",
  "published_at": "2026-05-28T09:31:00-04:00",
  "url": "https://...",
  "summary": "报道提到公司一季度业绩超预期，并给出更强的二季度产品收入增长指引。",
  "extracted_metrics": {
    "revenue": "1.39B USD",
    "revenue_surprise": "5.23%",
    "product_revenue_guidance_growth": "30%"
  },
  "confidence": 0.82
}
```

如果没有找到媒体证据，必须保存：

```json
{
  "type": "authoritative_media",
  "status": "not_found",
  "reason": "No whitelisted authoritative media found within the configured lookback window."
}
```

## 输出报告格式

每只触发股票输出：

- 股票代码和名称。
- 市场：A 股 / 港股 / 美股。
- 当前价格、涨跌幅、成交量变化。
- 信号类型：买入观察、继续持有、卖出观察、风险警报。
- 触发原因列表。
- 权威媒体证据列表。
- 基本面证据。
- 技术面证据。
- 建议动作。
- 止损/止盈或复核条件。
- 置信度。
- 数据缺口和风险提示。

示例：

```text
SNOW - buy_watch

触发原因：
1. 股价从近期低点连续反弹，今日放量上涨。
2. 权威媒体报道称一季度业绩超预期，营收高于预期约 5.23%。
3. 公司给出二季度产品收入同比约 30% 增长指引。

建议：
- 未持有：不追涨，等待回踩或二次确认。
- 已持有：继续持有，设置回撤止盈。
- 风险：若后续增长指引无法兑现，估值回撤风险较高。
```

## 调度计划

默认任务：

- A 股 watchlist：交易日 15:30 后运行。
- 美股 watchlist：美股收盘后运行，按服务器时区换算到北京时间。
- 开机补跑：系统启动时检查最近一次成功扫描时间；如果超过 24 小时则补跑一次。

资源控制：

- 每次最多深度分析 `10` 只候选股票。
- 每只股票最多保留 `20` 条新闻证据。
- 大模型只处理规则筛出的候选，不处理全量 watchlist。
- 如果行情或新闻源失败，保存降级原因并继续处理其他股票。

## UI 第一阶段

新增页面或扩展现有页面：

- Watchlist 管理：添加/删除股票，设置市场、标签、备注。
- 持仓管理：股票、成本价、持仓数量、目标价、止损价。
- 监控报告列表：按日期显示触发信号。
- 信号详情页：展示触发原因、媒体证据、建议、数据缺口。

第一阶段可以先做后端 API 和通知，UI 简化实现。

## API 第一阶段

建议新增：

- `GET /api/watchlists`
- `POST /api/watchlists`
- `DELETE /api/watchlists/{id}`
- `GET /api/portfolio/positions`
- `POST /api/portfolio/positions`
- `DELETE /api/portfolio/positions/{id}`
- `POST /api/monitoring/watchlist/run`
- `GET /api/monitoring/reports`
- `GET /api/monitoring/reports/{id}`

## 实施步骤

1. 建模和 API
   - 新增 watchlist 和 portfolio 数据模型。
   - 新增基础 CRUD API。
   - 新增 MongoDB 索引。

2. 规则引擎
   - 实现价格、成交量、趋势触发规则。
   - 先支持 watchlist，不做全市场。

3. 证据收集
   - 从已有新闻库查找相关新闻。
   - 接入 Alpha Vantage NEWS_SENTIMENT 或 Finnhub/Benzinga 的一种美股新闻源。
   - 对证据做来源白名单、时间窗口、关键词和 ticker 相关性评分。

4. 报告生成
   - 将价格、基本面、新闻证据交给大模型总结。
   - 要求输出结构化 JSON 和中文摘要。
   - 如果关键数据缺失，必须明确写出缺失项。

5. 调度和通知
   - 在 APScheduler 注册 `watchlist_monitor_daily`。
   - 写入 `monitoring_runs` 和 `monitoring_reports`。
   - 高优先级信号写入通知中心。

6. UI 最小闭环
   - Watchlist 页面。
   - 监控报告列表。
   - 报告详情。

7. 验证
   - 使用小 watchlist 验证：`SNOW`, `NVDA`, `MSFT`。
   - 验证无新闻、无行情、API 限流、模型失败时的降级行为。

## 验收标准

- [ ] 用户能维护 watchlist。
- [ ] 用户能维护持仓列表。
- [ ] 可以手动触发 watchlist 扫描。
- [ ] 可以每天自动运行一次 watchlist 扫描。
- [ ] 规则引擎能识别上涨机会、下跌风险、持仓卖出风险。
- [ ] 每条高优先级信号至少包含一条价格/成交量/趋势证据。
- [ ] 每条高优先级信号必须包含权威媒体证据，或明确记录未找到原因。
- [ ] 报告中不得只写“市场情绪好/基本面改善”，必须列出来源、标题、时间、URL 和提取出的关键指标。
- [ ] 通知中心能收到重要信号提醒。
- [ ] 模型输出需要保存到 `monitoring_reports`，原始证据保存到 `monitoring_evidence`。
- [ ] 对同一股票同一触发日去重，避免重复通知。

## 残余风险

- 权威媒体源通常需要付费 API；免费源可能延迟、限流或缺少摘要。
- Zacks 未确认可用官方 API，不应在第一阶段做非授权抓取。
- Alpha Vantage 新闻源可用，但媒体覆盖和延迟需要实测。
- Benzinga 新闻质量更适合美股异动解释，但可能需要单独付费。
- A 股公告和媒体证据质量与美股不同，需要单独设计 A 股证据权重。
- 大模型只能总结证据，不能作为事实来源；所有关键事实必须来自结构化证据或可追溯链接。

## 参考来源

- Alpha Vantage API Documentation: `https://www.alphavantage.co/documentation/`
- Benzinga Newsfeed API Overview: `https://docs.benzinga.com/api-reference/news-api/overview`
- Benzinga Get News API: `https://docs.benzinga.com/api-reference/news-api/get-news-items`
- Finnhub Company News API: `https://finnhub.io/docs/api/company-news`
- Finnhub Earnings Calendar API: `https://finnhub.io/docs/api/earnings-calendar`
