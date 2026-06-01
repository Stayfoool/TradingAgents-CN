# Harness Engineering

本项目的质量门禁分成轻量本地门禁和完整交付门禁，目标是让代码修改在进入分支前尽早暴露语法、回归、接口和前端构建问题。

## 当前状态

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| 统一质量入口 `quality_verify.py` | 已完成 | 后端、前端、E2E、pre-commit、扩展服务回归都有 profile。 |
| 本地 pre-commit 配置 | 已完成并安装 | `.pre-commit-config.yaml` 已存在，`.git/hooks/pre-commit` 已安装。 |
| Ruff | 已接入，覆盖范围有限 | 已纳入后端门禁，目前只检查质量门禁相关文件，后续逐步扩大。 |
| pytest 后端质量门禁 | 已完成并验证 | 临时 `uv` 质量环境下 `tests/quality` 通过。 |
| Schemathesis API 合约 smoke | 已完成并验证 | 已包含在 `tests/quality` 中。 |
| GitHub Actions 统一门禁 | 已配置，待远端运行确认 | Workflow 已改为调用 `quality_verify.py`。 |
| 前端 type-check / unit / build | 已完成并验证 | `frontend` profile 已通过；存在非阻塞 Sass 和 chunk-size 警告。 |
| Playwright E2E | 已有入口，待本轮重新验证 | `frontend-e2e` profile 已接入；本轮未重新跑浏览器测试。 |
| 扩展服务回归 `services` profile | 已有入口，未验证 | 用于更完整的服务级测试，可能需要完整依赖。 |
| Testcontainers / Docker Compose test profile | 未开始 | 后续用于真实 MongoDB/Redis 集成测试。 |
| 智能选股专项 harness | 未开始 | 等智能选股正式开发时补 DSL、Mongo 查询、文本事件、防未来数据测试。 |
| LLM 专项评测 Langfuse / DeepEval / Ragas | 未开始 | 后置，先保证数据和工具执行可靠。 |

## 本地门禁

安装质量依赖后启用 pre-commit：

```bash
python -m pip install -r requirements-quality.txt
pre-commit install
```

手动运行本地轻门禁：

```bash
python3 scripts/validation/quality_verify.py --profile precommit
```

轻门禁会执行：

- Python 语法检查，不写入 `__pycache__`
- Ruff 检查质量门禁相关文件
- 监控模块确定性 smoke gate

## 后端交付门禁

```bash
python3 scripts/validation/quality_verify.py --profile backend
```

等价 Makefile 入口：

```bash
make verify-backend
```

后端门禁会执行：

- Python 语法检查
- Ruff 检查质量门禁相关文件
- `scripts/validation/monitoring_quality_gate.py`
- `tests/quality`

扩展服务回归单独运行：

```bash
python3 scripts/validation/quality_verify.py --profile services
```

该 profile 会额外覆盖监控、筛选、行情入库、MongoDB 业务库解析相关测试。它比默认后端门禁更接近业务模块，因此可能需要更完整的本地依赖。

## 前端交付门禁

先安装前端依赖：

```bash
cd frontend
yarn install --frozen-lockfile --production=false --network-timeout 300000
```

运行前端门禁：

```bash
python3 scripts/validation/quality_verify.py --profile frontend
```

前端门禁会执行：

- `yarn type-check`
- `yarn test:unit`
- `yarn vite build`

浏览器端到端测试单独运行：

```bash
python3 scripts/validation/quality_verify.py --profile frontend-e2e
```

## CI

GitHub Actions 使用同一个 `quality_verify.py` 入口，避免本地、华为云和远端 CI 各跑一套不同命令。

## 扩展原则

- 新增功能时，优先把固定回归样例加入 `tests/quality` 或聚焦服务测试。
- 对智能选股功能，后续新增 DSL golden tests、Mongo 查询构造测试和文本事件防未来数据测试。
- Ruff 当前只覆盖质量门禁相关文件，避免历史代码问题一次性阻塞交付；后续可以逐步扩大覆盖范围。
