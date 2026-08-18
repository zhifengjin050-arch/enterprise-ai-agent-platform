# GitHub Release Checklist — v1.0.0

- [x] README
- [x] English README
- [x] Architecture Diagram
- [x] Screenshots
- [x] Demo
- [x] Docker
- [x] Kubernetes
- [x] Helm
- [x] CI
- [x] Security

验证日期：2026-08-18。详见 [FINAL_RELEASE_REPORT.md](FINAL_RELEASE_REPORT.md)。

## Documentation

- [x] `README.md`（简介、核心能力、Feature Matrix、架构、截图、快速启动、Docker / K8s / Helm、API 示例、测试结果、Roadmap）
- [x] `README_EN.md`
- [x] `docs/images/system_architecture.md`（含 Security / Observability / MCP Layer）
- [x] `docs/images/hero.png`
- [x] `docs/images/architecture_overview.png`
- [x] `docs/RELEASE_GUIDE.md`
- [x] `docs/GITHUB_PUBLISH.md`
- [x] `CHANGELOG.md`

## Screenshots

| File | Notes |
|------|--------|
| `01_dashboard.png` | 运行时 `/` |
| `02_agent_chat.png` | 运行时 `/agents` |
| `03_knowledge_search.png` | 运行时 `/knowledge` |
| `04_workflow.png` | 运行时 `/workflows` |
| `05_connector.png` | Product Preview（无独立路由） |
| `06_observability.png` | 运行时 `/monitor` |
| `07_security.png` | Product Preview（无独立路由） |

## Open source metadata

- [x] `LICENSE` Apache-2.0
- [x] `.gitignore`（`.env` `*.db` `*.sqlite` `logs/` `*.log` `node_modules/` `dist/` `build/` `__pycache__/` `.pytest_cache/`）
- [x] `CONTRIBUTING.md` / `SECURITY.md` / `CODE_OF_CONDUCT.md`
- [x] `.github/workflows/ci.yml`
- [x] `.github/ISSUE_TEMPLATE/bug_report.md` / `feature_request.md`
- [x] `.github/PULL_REQUEST_TEMPLATE.md`

## Verification

| Check | Result |
|-------|--------|
| `python -m compileall app/` | success |
| pytest 稳定套件 | **998 passed, 3 skipped** |
| `cd frontend && npm run build` | success |

未新增产品功能，未改核心架构，未改测试断言。
