# Enterprise Observability & AI Operations Platform — Phase 8

> 企业级 AI 平台可观测性架构设计文档。

---

## 1. 概述

Phase 8 在企业级 SaaS 安全体系（Phase 7）之上，建设完整的可观测性体系，使平台具备商业交付级别的监控、追踪、成本分析和告警能力。

### 设计原则

- **旁路增强** — 不破坏现有 Connector / SyncEngine / Knowledge / Agent Runtime / Security
- **增量演进** — 增强而非重写现有 logging / cost / metrics
- **开放标准** — OpenTelemetry Tracing + Prometheus Metrics + Grafana Dashboards
- **租户隔离** — 所有可观测数据通过 `tenant_id` 隔离，监控 API 需要 `admin.monitor` 权限

---

## 2. OpenTelemetry Tracing

### 架构

```
┌──────────────────────────────────────────────┐
│           TraceManager (app/observability/)   │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│  │ start_span│  │current_  │  │get_trace_id│ │
│  │          │  │span      │  │get_span_id │ │
│  └──────────┘  └──────────┘  └────────────┘ │
│                                              │
│  OTEL SDK (optional — gracefully degrades)   │
│  OTLP Exporter → Collector → Jaeger/Tempo    │
└──────────────────────────────────────────────┘
```

### Trace 范围

| Trace 名称 | 组件 | 关键属性 |
|---|---|---|
| `http.request` | HTTP 请求 | tenant_id, user_id, method, endpoint |
| `agent.execute` | Agent 执行 | agent_id, task_id, tenant_id |
| `llm.call` | LLM 调用 | provider, model, tenant_id |
| `tool.execute` | 工具调用 | tool_name, task_id |
| `knowledge.retrieve` | 知识检索 | search_type, tenant_id |
| `sync.job` | 同步任务 | connector_type, sync_mode |
| `connector.sync` | Connector 同步 | connector_id |

### Span 字段

- `trace_id` — 64 位 hex
- `span_id` — 32 位 hex
- `tenant_id` — 从 TenantContext 自动注入
- `user_id` — 从 TenantContext 自动注入
- `agent_id` / `task_id` — 由调用方设置

### 降级策略

当 `opentelemetry` 包未安装时，`TraceManager` 返回 `_NoopSpan`，应用无感知。

---

## 3. Prometheus Metrics

### 指标清单

#### HTTP

| 指标名 | 类型 | 标签 |
|---|---|---|
| `http_requests_total` | Counter | method, endpoint, status |
| `http_request_duration_seconds` | Histogram | method, endpoint |

#### Agent

| 指标名 | 类型 | 标签 |
|---|---|---|
| `agent_tasks_total` | Counter | agent_type, status |
| `agent_task_duration_seconds` | Histogram | agent_type |
| `agent_failures_total` | Counter | agent_type, error_code |

#### LLM

| 指标名 | 类型 | 标签 |
|---|---|---|
| `llm_requests_total` | Counter | provider, model, request_type |
| `llm_request_duration_seconds` | Histogram | provider, model |
| `llm_tokens_input_total` | Counter | provider, model |
| `llm_tokens_output_total` | Counter | provider, model |

#### Knowledge

| 指标名 | 类型 | 标签 |
|---|---|---|
| `knowledge_retrievals_total` | Counter | search_type |
| `knowledge_retrieval_duration_seconds` | Histogram | search_type |

#### Sync

| 指标名 | 类型 | 标签 |
|---|---|---|
| `sync_jobs_total` | Counter | connector_type, sync_mode, status |
| `sync_job_duration_seconds` | Histogram | connector_type |
| `sync_failures_total` | Counter | connector_type |

#### System

| 指标名 | 类型 | 说明 |
|---|---|---|
| `active_agents` | Gauge | 当前运行中 Agent 数 |
| `active_sync_jobs` | Gauge | 当前运行中 Sync 数 |
| `uptime_seconds` | Gauge | 服务运行时长 |

### 端点

`GET /metrics` — Prometheus text format，已有 `app/monitor/metrics.py`，Phase 8 新增指标在 `app/observability/metrics.py`。

---

## 4. Structured Logging 升级

### 日志格式

每个日志条目为单行 JSON：

```json
{
  "timestamp": "2026-08-18T12:00:00.000Z",
  "level": "INFO",
  "service": "enterprise-knowledge-agent",
  "module": "app.api.health",
  "message": "Health check passed",
  "request_id": "abc-123",
  "trace_id": "0af7651916cd43dd8448eb211c80319c",
  "tenant_id": "t-001",
  "user_id": "u-001",
  "extra": {},
  "exception": null
}
```

### 字段说明

| 字段 | 必须 | 来源 |
|---|---|---|
| `timestamp` | 是 | UTC ISO8601 |
| `level` | 是 | LogRecord.levelname |
| `service` | 是 | 常量 `enterprise-knowledge-agent` |
| `module` | 是 | LogRecord.name |
| `message` | 是 | LogRecord.getMessage() |
| `request_id` | 推荐 | logging extra 或 RequestIDMiddleware 传递 |
| `trace_id` | 自动 | TraceManager.get_trace_id() |
| `tenant_id` | 推荐 | extra 或 TenantContext |
| `user_id` | 推荐 | extra 或 TenantContext |
| `extra` | 可选 | 非标准 LogRecord 属性 |
| `exception` | 异常时 | traceback 内容 |

### 禁止项

- `print()` — 统一使用 `get_logger(__name__)`
- 裸 `except Exception: pass` — 必须记录日志

---

## 5. LLM Cost Tracking

### 数据模型

`llm_usage_records` 表：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | String(36) | UUID PK |
| tenant_id | String(36) | 租户 ID，index |
| user_id | String(36) | 用户 ID，index |
| agent_id | String(36) | Agent ID，index |
| task_id | String(36) | 任务 ID，index |
| provider | String(50) | deepseek / openai / ... |
| model | String(100) | deepseek-chat / gpt-4 |
| request_type | String(50) | chat / embedding / ... |
| prompt_tokens | Integer | 输入 token 数 |
| completion_tokens | Integer | 输出 token 数 |
| total_tokens | Integer | 总 token 数 |
| estimated_cost | Float | 估算 USD 费用 |
| created_at | DateTime | 记录时间，index |

### 成本统计

- 按租户统计：`LLMUsageTracker.summary(tenant_id=xxx)`
- 按用户统计：`LLMUsageTracker.query(user_id=xxx)`
- 按 Agent 统计：`LLMUsageTracker.query(agent_id=xxx)`

### 向后兼容

`app/observability/cost_tracker.py` 同时写入新旧两表：
- 新表 `llm_usage_records`（丰富字段 + 归属信息）
- 旧表 `llm_cost_records`（通过 `CostRepository`）

---

## 6. Agent Debug Trace

### 数据模型

`agent_execution_traces` 表：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | String(36) | UUID PK |
| task_id | String(36) | 任务 ID，index |
| tenant_id | String(36) | 租户 ID，index |
| step | Integer | 步骤序号 |
| component | String(50) | planner / tool / retriever / llm / final |
| input_json | JSON | 步骤输入 |
| output_json | JSON | 步骤输出 |
| latency_ms | Integer | 步骤耗时 |
| success | Boolean | 是否成功 |
| error | Text | 错误消息 |
| created_at | DateTime | 记录时间，index |

### 追踪链路

```
Task
│
├─ Planner   (step=1, component="planner")
│
├─ Tool Call (step=2, component="tool")
│
├─ Retriever (step=3, component="retriever")
│
├─ LLM       (step=4, component="llm")
│
└─ Final     (step=5, component="final")
```

---

## 7. Dashboard API

### 端点列表

| 端点 | 权限 | 说明 |
|---|---|---|
| `GET /api/metrics/overview` | `admin.monitor` | 系统健康概览 + 24h 聚合 |
| `GET /api/metrics/agents` | `admin.monitor` | Agent 执行统计 + 成功率 |
| `GET /api/metrics/llm` | `admin.monitor` | LLM 消耗统计（per model） |
| `GET /api/metrics/sync` | `admin.monitor` | 同步任务状态 + 成功率 |
| `GET /api/metrics/errors` | `admin.monitor` | 错误统计（per component） |

所有端点返回数据受 `tenant_id` 隔离。

---

## 8. Health Check

### 端点

`GET /api/health`

### 检测项

| 组件 | 检测方式 | 状态值 |
|---|---|---|
| database | `SELECT 1` 异步执行 | healthy / unhealthy |
| vector_store | ChromaDB heartbeat API | healthy / degraded / unhealthy |
| llm | LLM base URL 连通性 | healthy / degraded / not_configured |
| connector_feishu | 凭据存在性 | healthy / not_configured |
| connector_yuque | 凭据存在性 | healthy / not_configured |
| redis | Socket 连通性（localhost:6379） | healthy / not_configured |

### 总体状态

- **healthy**: 所有组件 healthy 或 not_configured
- **degraded**: 至少一个组件 degraded，无 unhealthy
- **unhealthy**: 至少一个组件 unhealthy

---

## 9. Alert Rules

| 规则名 | 表达式 | 严重度 | 说明 |
|---|---|---|---|
| HighAPIErrorRate | 5xx 比例 > 5% | critical | API 错误率过高 |
| HighLLMFailureRate | LLM 失败率 > 3% | warning | LLM 调用异常 |
| SyncFailureRateHigh | 同步失败率 > 0.1/s | warning | 同步异常 |
| TokenGrowthAnomaly | Token 输入速率突增 3x | warning | 异常 Token 消耗 |
| DatabaseUnhealthy | 数据库不可达 | critical | 数据库故障 |

---

## 10. 数据库 Migration

### Migration 0010

新增三张表：
- `llm_usage_records` — LLM 用量记录（替代增强 `llm_cost_records`）
- `agent_execution_traces` — Agent 步骤级调试追踪
- `system_events` — 系统事件 / 告警记录

所有表包含 `tenant_id` + `created_at` 索引。

---

## 11. Security Integration

### API 安全

所有 `/api/metrics/*` 端点受 `require_permission("admin.monitor")` 保护。

### 数据隔离

- `llm_usage_records.tenant_id` — 查询时自动过滤
- `agent_execution_traces.tenant_id` — 查询时自动过滤
- `system_events.tenant_id` — 查询时自动过滤

### 权限定义

```python
PERMISSION_CODES = {
    # ...
    "admin.monitor": "访问监控仪表盘和指标 API",
}
```

---

## 12. 部署配置

### Prometheus

- 配置文件: `deploy/monitoring/prometheus.yml`
- 抓取间隔: 15s
- 告警规则: `deploy/monitoring/alerts.yml`

### Grafana

- Dashboard JSON: `deploy/monitoring/grafana/dashboard.json`
- 包含面板: System Overview, AI Overview, Knowledge & Sync

---

## 13. 测试策略

- `tests/observability/test_trace.py` — TraceManager 单元 + 模型
- `tests/observability/test_metrics.py` — Prometheus 指标定义 + 录制
- `tests/observability/test_cost.py` — LLMUsageTracker 读写 + 聚合
- `tests/observability/test_health.py` — Health API + Monitor API
- `tests/observability/test_dashboard.py` — Metrics API 端点
- `tests/observability/test_alert.py` — AlertEngine 写入 + 评估
- `tests/observability/test_agent_debug.py` — AgentDebugRecorder
- `tests/observability/test_logging.py` — StructuredFormatter 升级

要求: 100+ 测试用例覆盖。

---

## 14. 架构分层

```
┌──────────────────────────────────────────────────┐
│                   API Layer                       │
│  /api/health  /api/metrics/*  /metrics           │
├──────────────────────────────────────────────────┤
│             Observability Layer                   │
│  ┌──────────┐ ┌──────────┐ ┌───────────────────┐ │
│  │ Trace    │ │ Metrics  │ │ Agent Debug Trace │ │
│  │ Manager  │ │Collector │ │ (LLMUsageTracker) │ │
│  └──────────┘ └──────────┘ └───────────────────┘ │
├──────────────────────────────────────────────────┤
│           Data Persistence Layer                  │
│  ┌─────────────────┐ ┌─────────────────────────┐ │
│  │ llm_usage_records│ │agent_execution_traces   │ │
│  │ system_events   │ │                         │ │
│  └─────────────────┘ └─────────────────────────┘ │
├──────────────────────────────────────────────────┤
│           External Systems                        │
│  Prometheus → Grafana / AlertManager              │
│  OpenTelemetry → Jaeger / Tempo                   │
└──────────────────────────────────────────────────┘
```

---

## 15. 向后兼容性

| 现有组件 | Phase 8 变更 |
|---|---|
| `app/core/logging/formatter.py` | 升级：增加 timestamp/service/trace_id 字段 |
| `app/monitor/metrics.py` | 保留不变，`app/observability/metrics.py` 新增指标 |
| `app/llm/cost/tracker.py` | 保留不变，`app/observability/cost_tracker.py` 同时写入新旧表 |
| `app/agent_runtime/trace.py` | 保留不变，`app/observability/agent_debug.py` 提供持久化版本 |
| `app/api/health.py` | 升级：增加组件级检查 + trace_id |
| `app/api/monitor.py` | 保留不变 |

---

*文档版本: v0.9.0 — Enterprise Observability & AI Operations Platform*