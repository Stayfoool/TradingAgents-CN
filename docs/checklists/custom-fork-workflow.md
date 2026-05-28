# Custom Fork Workflow Checklist

Date: 2026-05-28

## Repository Remotes

- [x] `origin` points to the personal fork: `https://github.com/Stayfoool/TradingAgents-CN.git`
- [x] `upstream` points to the original project: `https://github.com/hsliuping/TradingAgents-CN.git`
- [x] `upstream` push URL is disabled to avoid accidental pushes to the original project.

## Branching

- [x] Local custom development branch created: `dev/custom-stock-agent`
- [x] Current custom code changes are staged for this branch.

## Included Custom Changes

- [x] DeepSeek/Qwen/Zhipu model detection improved for news prefetching.
- [x] Data-source API key logging changed from raw value to masked value.
- [x] Huawei Cloud backend Dockerfile added with Huawei Debian mirror.
- [x] Local backend build compose override added.
- [x] MongoDB and Redis external port exposure disabled in compose override.

## Verification

- [x] Python syntax check passed for changed Python files with `python3 -m compileall`.
- [x] Huawei Cloud backend was rebuilt from the same code changes and health check passed.
- [x] Changes pushed to GitHub fork.
- [x] Huawei Cloud repository remote switched to the personal fork.
- [x] Huawei Cloud repository checked out to `dev/custom-stock-agent`.

## Residual Risks

- GitHub SSH from this network is blocked, so HTTPS remotes are used.
- Huawei Cloud fetch from GitHub over HTTPS may be unstable; a local Git bundle was used once to seed `origin/dev/custom-stock-agent`.
- Huawei Cloud still has an untracked backup file: `Dockerfile.backend.upstream`.
