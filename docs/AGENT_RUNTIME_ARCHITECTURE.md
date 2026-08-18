# Agent Runtime Architecture

## 概述

Phase 6 将系统升级为 **Enterprise AI Agent Platform**，新增统一执行框架 `app/agent_runtime/`，
在不破坏 Connector / SyncEngine / Knowledge Intelligence 的前提下，提供：

Planner → Tool System → Memory → LLM Gateway → SSE Streaming

```
                 User
                  |
              API Gateway
                  |
          Enterprise Agent Runtime
                  |
    +-------------+-------------+
    |             |             |
 Planner      Tool System   Memory
    |             |
 LLM Gateway   Knowledge Tools
                  |
          Knowledge Intelligence
                  |
       RAG + Graph + Documents
```

**兼容说明：**

| 组件 | 路径 | 状态 |
|------|------|------|
| 旧 KnowledgeAgent | `app/agent/` + `/api/agent/chat` | **保留** |
| 新 Agent Runtime | `app/agent_runtime/` + `/api/agents/*` | **新增** |
| 静态 Prompt | `app/prompts/` | **保留** |
| DB Prompt | `app/prompt/` | **新增** |
| LLM Client | `app/llm/client.py` | **保留**，由 Gateway wrap |

---

## 包结构

```
app/agent_runtime/
  agent.py          # BaseAgent 生命周期
  models.py         # ORM + AgentResult / ExecutionPlan
  planner.py        # TaskPlanner
  memory.py         # AgentMemoryManager
  context.py        # ContextEngine
  trace.py          # AgentTrace
  tools/
    base.py
    registry.py
    knowledge_search.py
    graph_query.py
    document_query.py
    connector_sync.py

app/llm/gateway.py  # LLMProvider / ModelRouter / LLMGateway
app/prompt/         # PromptTemplate + PromptManager
app/api/agents.py   # /api/agents REST + SSE
```

---

## Agent 生命周期

```
CREATED → INITIALIZED → RUNNING → (WAITING) → COMPLETED
                                         ↘ FAILED
```

| 方法 | 说明 |
|------|------|
| `initialize()` | 加载 LLM Gateway 等资源 |
| `execute(input)` | 规划 → 执行工具 → 合成答案 |
| `stream(input)` | 产出 thinking / tool_call / retrieval / answer 事件 |
| `cleanup()` | 释放状态 |

---

## Planner

`TaskPlanner.plan(query)` → `ExecutionPlan`

规则示例（可替换为 LLM Planner，契约不变）：

- 默认：`knowledge_search`
- K8s / 依赖：追加 `graph_query`
- OOM / 故障：追加故障类 `knowledge_search`
- 同步：追加 `connector_sync`（无 `connector_id` 时 Runtime 跳过）

---

## Tool 开发规范

1. 继承 `BaseTool`，设置 `name` / `description` / `permissions`
2. 实现 `async execute(input, context) -> ToolResult`
3. 通过 `ToolRegistry.register()` 注册
4. 工具内捕获异常，返回 `ToolResult(success=False)`，避免击穿 Runtime
5. 需要 DB 时使用 `context.session`

内置工具：

| Tool | 权限 | 依赖 |
|------|------|------|
| `knowledge_search` | knowledge.read | KnowledgeRetriever |
| `graph_query` | knowledge.read | KnowledgeGraph |
| `document_query` | knowledge.read | KnowledgeRepository |
| `connector_sync` | connector.sync | SyncWorker |

---

## LLM 扩展规范

1. 实现 `LLMProvider`：`chat` / `stream` / `embedding` / `get_model_name`
2. `ModelRouter.register(key, provider)`
3. 通过 `LLMGateway` 访问，**不要**在 Agent 内直接调厂商 SDK

路由默认：

| 复杂度 | 优先 Provider |
|--------|---------------|
| simple | deepseek |
| complex | claude → openai → qwen |
| embedding | bge / embedding |

---

## Memory 设计

`AgentMemoryManager`：

- **短期**：`ConversationMemory`（最近 10 轮）
- **检索缓存**：Phase 5 `KnowledgeMemory` LRU
- **长期**：`agent_messages` 表（PostgreSQL）

---

## Prompt 管理

`prompt_templates` 表字段：`id, name, version, content, system_prompt, variables, metadata, tenant_id, created_at`

`PromptManager.create / get_by_name / render`

与 `app/prompts` 静态模板并存。

---

## API 说明

权限码：`agent.read` / `agent.write` / `agent.execute`

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/agents` | 创建 Agent |
| GET | `/api/agents` | 列表 |
| POST | `/api/agents/{id}/execute` | 执行任务 |
| GET | `/api/agents/{id}/history` | 任务/消息历史 |
| POST | `/api/agents/chat` | SSE 流式聊天 |

SSE 事件：

```json
{"type":"thinking","content":"..."}
{"type":"tool_call","name":"knowledge_search"}
{"type":"retrieval","count":5,"data":[...]}
{"type":"answer","content":"...","sources":[...]}
```

---

## 数据库（migration `0008_agent_runtime`）

表：`agents`、`agent_tasks`、`agent_messages`、`agent_tool_calls`、`prompt_templates`

- 全部含 `tenant_id`（prompt / agents / tasks / messages / tool_calls）
- FK：`agent_tasks.agent_id → agents.id`，messages/tool_calls → tasks/agents
- 关键 index 覆盖 tenant / status / conversation_id / tool_name

---

## 安全

异常（Phase 2 体系）：

- `AgentPermissionException`
- `ToolPermissionException`
- `LLMQuotaException`
- `AgentNotFoundException` / `ToolNotFoundException` / `AgentExecutionException`

所有 `/api/agents` 路由使用 `require_permission()`。

---

## 可观测性

`AgentTrace` 记录：`task_id` / `agent` / `model` / `tokens` / `latency_ms` / `tools`

结果写入 `AgentResult.metadata["trace"]`，便于后续对接 Prometheus / Grafana / OpenTelemetry。

---

## 测试

```bash
pytest tests/agent_runtime/ -q
python -m compileall app/agent_runtime app/llm/gateway.py app/prompt app/api/agents.py
```
