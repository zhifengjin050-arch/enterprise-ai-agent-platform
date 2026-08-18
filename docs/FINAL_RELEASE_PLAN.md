# Enterprise AI Agent Platform v1.0 RC — 最终发布计划

> 基于 2026-08-18 项目全面审计结果制定。

---

## 当前状态摘要

| 维度 | 数据 |
|------|------|
| **测试用例** | ~1219 collected, 997 passed, 1 failed, 3 skipped, 6 warnings |
| **代码规模** | app/ 目录 ~239 个 .py 文件 |
| **已知失败** | `test_cache_max_size_eviction` — LRU 驱逐 Bug |
| **已知挂起** | workflow engine 测试 (approval 超时后台任务 vs 测试 DB 冲突) |
| **文档** | 9 份架构文档，但无展示/求职材料 |
| **版本** | `app/main.py` 中 3 处版本字符串不一致 (0.10.0 / 0.10.0 / 1.0.0) |
| **前端** | Vite + React 19 + Tailwind v4 + shadcn/ui, 5 页面完成 |
| **Docker** | 7 服务: backend, frontend, postgres, redis, chroma, prometheus, grafana |
| **K8s** | 6 个 manifests + Helm Chart (12 文件) |
| **MCP** | 6 模块: client/adapter/registry/discovery/router 全部完成 |
| **Demo 数据** | 5 份 Markdown + init_demo_data.py |

---

## 执行路线图

```
Day 1 ── Phase A: 修复质量问题
  ├── Fix test_cache LRU eviction bug
  ├── Add pytest-timeout for CI safety
  └── Configure ruff/bandit quality gates

Day 2 ── Phase B: 制作展示材料
  ├── PROJECT_OVERVIEW.md
  ├── ARCHITECTURE_OVERVIEW.md (最终架构图)
  └── FEATURE_MATRIX.md

Day 3 ── Phase C: Demo 数据
  ├── 确认 5 份文档内容完备
  └── scripts/demo_init.py 整合

Day 3 ── Phase D: README 重构
  ├── GitHub 企业级 README
  ├── 截图占位 + 完整快速开始
  └── 版本统一

Day 3 ── Phase E: 求职材料
  ├── PROJECT_RESUME.md (SRE/DevOps/AI/后端四方向)
  └── 面试介绍版本 (3/5/10 分钟)

Day 3 ── Phase F: 发布清单
  └── RELEASE_CHECKLIST.md
```

---

## Phase A：修复质量问题

### A-1. 修复 test_cache LRU 驱逐

**问题**: `test_cache_max_size_eviction` — `max_size=3` 时插入 4 个键，`get_cache("a")` 期望 `None` 但返回 `1`。

**根因定位**: 查看 `app/llm/cache.py` 的 LRU 实现。

**要求**: 修复真实 LRU 逻辑，不降低测试标准。

### A-2. 添加 pytest-timeout

**问题**: workflow 测试在某些环境下无限挂起 (approval_service 后台超时任务 vs 测试 DB session 冲突)。

**方案**: 
- 安装 `pytest-timeout`
- `pytest.ini` 添加全局 120s 超时
- CI 不再无限等待

### A-3. 代码质量门禁

- `pyproject.toml` 中统一 ruff 配置 (移除 `ruff.toml` 避免重复)
- 运行 `ruff check` 记录当前问题，不强制大规模修复
- 添加 `bandit` 配置做安全基线
- 运行 `mypy` 记录类型覆盖率

---

## Phase B：展示材料

**目录**: `docs/showcase/`

### B-1. PROJECT_OVERVIEW.md
- 项目定位：Enterprise AI Agent Platform
- 一句话介绍
- 核心能力一览
- 与竞品对比 (n8n, Dify, LangGraph)

### B-2. ARCHITECTURE_OVERVIEW.md
- 最终架构图 (Mermaid)
- 层级说明
- 数据流

### B-3. FEATURE_MATRIX.md
- 完整能力矩阵表
- Connector/Sync/RAG/Graph/Agent/Workflow/Security/Observability/Deployment
- 每项标注状态

---

## Phase C：Demo 数据

现有:
- `examples/demo/documents/` 5 份文档 ✅
- `scripts/init_demo_data.py` ✅

需要:
- 确认文档内容为企业级模板
- `scripts/demo_init.py` 作为用户友好入口 (别名)

---

## Phase D：README 重构

现有 README 已较完善，需：
- 统一版本号 (全部改为 1.0.0)
- 添加截图占位 (使用 `docs/showcase/screenshots/`)
- 添加 GitHub 徽章 (指向 CI passing)
- 强化「不是聊天机器人」定位
- 添加「谁应该使用」章节

---

## Phase E：求职材料

**目录**: `docs/career/`

### E-1. PROJECT_RESUME.md
- 项目一句话描述
- 4 个方向分别包装 (SRE/DevOps/AI/后端)
- 关键技术关键词
- 面试介绍稿 (3/5/10 分钟)

---

## Phase F：发布清单

**文件**: `RELEASE_CHECKLIST.md`

| 分类 | 检查项 |
|------|--------|
| 代码 | tests pass, compileall, lint |
| 部署 | docker compose, .env.example |
| 文档 | README, Architecture, Demo |
| 求职 | Resume, Screenshots, Interview Notes |

---

## 时间估算

| Phase | 预计耗时 | 并行度 |
|-------|----------|--------|
| A-1 (fix test_cache) | 30-60min | 串行 |
| A-2 (pytest-timeout) | 5min | A-1 并行 |
| A-3 (ruff/bandit) | 15min | A-1 并行 |
| B (展示材料) | 60min | 串行 |
| C (Demo 确认) | 15min | B 并行 |
| D (README 重构) | 30min | 串行 |
| E (求职材料) | 45min | 串行 |
| F (发布清单) | 10min | 并行 |
| **总计** | **~3-4 小时** | **2 天内可完成** |

---

## 最终验证

完成后运行：

```bash
pytest tests/ -v --tb=short -q                          # 1000+ passed
python -m compileall app/                                # 无编译错误
ruff check app/                                          # 无新问题
cd frontend && npm run build && cd ..                    # 前端构建 OK
docker compose build                                     # Docker 构建 OK
```