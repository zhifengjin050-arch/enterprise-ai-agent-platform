# Enterprise AI Workflow Automation Engine — Architecture

> Phase 9 of the Enterprise AI Automation Platform  
> Builds on: Agent Runtime, Tool System, Knowledge Intelligence, Multi-Tenant SaaS, Observability

---

## 1. Overview

The Workflow Engine provides a general-purpose, enterprise-grade orchestration platform for defining, executing, and managing AI workflows. It replaces ad-hoc pipeline logic with a reusable JSON DSL engine that supports human-in-the-loop, event-driven triggers, and full observability integration.

### Design Goals

- **Declarative**: Workflows are defined as JSON DSL — no coding required.
- **Extensible**: Plug in new node types via a simple `Node` interface.
- **Resilient**: Pause, resume, cancel, retry, and timeout support.
- **Observable**: Every execution emits traces, metrics, and audit events.
- **Multi-Tenant**: Full `tenant_id` isolation on every table and operation.
- **Secure**: RBAC via `admin.workflow` permission, webhook HMAC validation.

---

## 2. Module Layout

```
app/workflow_engine/
├── __init__.py          # Public API exports
├── models.py            # SQLAlchemy ORM: WorkflowDefinition, WorkflowNode, WorkflowExecution, WorkflowEvent
├── parser.py            # JSON DSL parser + validator
├── nodes.py             # Node ABC + TriggerNode, AgentNode, ToolNode, ConditionNode, ApprovalNode, EndNode
├── engine.py            # WorkflowEngine — orchestration core
├── trigger.py           # ApiTrigger, WebhookTrigger, ScheduleTrigger, SyncEventTrigger, TriggerManager
├── approval.py          # ApprovalService — human-in-the-loop with timeout
└── observability.py     # Workflow-specific tracing, metrics, audit logging

alembic/versions/
└── 0011_workflow.py     # Migration creating workflows, workflow_nodes, workflow_executions, workflow_events

tests/workflow/
├── conftest.py          # Fixtures + sample workflow definitions
├── test_parser.py       # DSL validation tests
├── test_nodes.py        # Node execution tests
├── test_trigger.py      # Trigger validation + extraction tests
├── test_approval.py     # ApprovalService tests (create, approve, reject, timeout, callbacks)
├── test_engine.py       # WorkflowEngine lifecycle tests (CRUD, execute, pause, resume, cancel)
├── test_api.py          # REST API endpoint tests
├── test_observability.py# Observability integration smoke tests
└── test_models.py       # ORM model persistence tests
```

---

## 3. Workflow Lifecycle

```
CREATED ──► RUNNING ──► COMPLETED
                │
                ├──► WAITING ◄──► PAUSED ◄──► RUNNING
                │       │
                │       ├──► (approval approved) ──► RUNNING
                │       └──► (approval rejected) ──► FAILED
                │
                └──► FAILED
```

| Status      | Description |
|-------------|-------------|
| `CREATED`   | Definition saved, not yet executed |
| `RUNNING`   | Execution in progress |
| `WAITING`   | Waiting for external input (e.g., approval) |
| `PAUSED`    | Execution paused by user |
| `COMPLETED` | All nodes executed successfully |
| `FAILED`    | Execution terminated with error |

---

## 4. JSON DSL

A workflow is defined as a JSON object with a `nodes` array:

```json
{
  "name": "Incident Auto-Resolution",
  "description": "Automatically analyze and resolve incidents",
  "version": "1.0",
  "trigger_type": "webhook",
  "trigger_config": { "secret": "whsec_..." },
  "timeout_seconds": 600,
  "max_retries": 2,
  "tags": ["devops", "incident"],
  "nodes": [
    { "type": "trigger", "name": "start" },
    {
      "type": "agent",
      "name": "analyze",
      "config": { "agent_name": "incident_agent", "task": "Analyze the incident" }
    },
    {
      "type": "tool",
      "name": "restart_pod",
      "config": { "tool_name": "k8s_restart", "params": { "namespace": "production" } }
    },
    {
      "type": "approval",
      "name": "human_review",
      "config": { "approvers": ["admin"], "message": "Approve restart?" }
    },
    { "type": "end", "name": "finish" }
  ]
}
```

### Node Types

| Type        | Description |
|-------------|-------------|
| `trigger`   | Entry point; seeds context from payload |
| `agent`     | Invokes Agent Runtime (Planner → Tool → Memory → LLM) |
| `tool`      | Executes a registered tool via ToolRegistry |
| `condition` | Evaluates a Python expression; routes to true/false branch |
| `approval`  | Human-in-the-loop gate; waits for approve/reject |
| `end`       | Terminal node; marks workflow complete |

---

## 5. Node Interface

Every node implements `async def execute(context: NodeContext) -> Dict[str, Any]`:

```python
class Node(ABC):
    def __init__(self, name: str, config: Optional[Dict] = None): ...
    @abstractmethod
    async def execute(self, context: NodeContext) -> Dict[str, Any]: ...
```

Result format:
```python
{
    "status": "success" | "failure" | "waiting",
    "output": {...} | None,
    "error": "..." | None
}
```

---

## 6. Event Triggers

| Trigger       | Description |
|---------------|-------------|
| `api`         | Manual / API invocation (always valid) |
| `webhook`     | HMAC-SHA256 signed payload validation |
| `schedule`    | Cron-based scheduled execution |
| `sync_event`  | Internal Sync Engine events (Git push, doc sync) |

### Example: GitLab Commit → Workflow → Agent Analysis → Report

```
GitLab webhook
    │
    ▼
TriggerManager.validate("webhook", payload, headers)
    │
    ▼
WorkflowEngine.execute(workflow_id, trigger_type="webhook")
    │
    ▼
TriggerNode seeds context with payload
    │
    ▼
AgentNode calls incident_agent for analysis
    │
    ▼
ToolNode generates report (e.g., sends to Feishu/Slack)
    │
    ▼
EndNode marks completion
```

---

## 7. Human Approval

`ApprovalService` manages the full approval lifecycle:

- **Create**: `create_approval(...)` → returns PENDING record
- **Approve**: `approve(approval_id, user_id, comment)` → fires callback
- **Reject**: `reject(approval_id, user_id, comment)` → fires callback
- **Timeout**: Background loop auto-expires stale approvals after configurable minutes
- **Callback**: Registered callbacks enable the WorkflowEngine to resume/cancel the run

---

## 8. Agent Integration

`AgentNode` wraps the existing Agent Runtime:

1. Resolves input from config or context variables
2. Attempts to call `AgentRuntime.arun(task)` (with graceful fallback)
3. Stores output in context under configurable `output_key`
4. Returns structured result with agent name and output

The Agent Runtime components (Planner, Tool, Memory, LLM) are all accessible through the existing `app/agent` module.

---

## 9. Observability Integration

Every workflow execution emits:

### Traces (OpenTelemetry)
- `workflow.execute` span with `workflow_id`, `run_id`, `status`
- Per-node spans: `workflow.{node_name}` with node-level attributes

### Metrics (Prometheus)
| Metric | Type | Labels |
|--------|------|--------|
| `workflow_execution_total` | Counter | status, trigger_type, tenant_id |
| `workflow_execution_duration_seconds` | Histogram | workflow_id, status |
| `workflow_node_execution_total` | Counter | node_type, status, tenant_id |

### Audit Events
- `workflow_events` table records every state transition
- Structured JSON logging via `log_workflow_event()`

---

## 10. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/workflows` | Create workflow definition |
| GET | `/api/workflows` | List workflow definitions |
| GET | `/api/workflows/{id}` | Get workflow definition |
| POST | `/api/workflows/{id}/execute` | Execute (start) workflow |
| GET | `/api/workflows/{id}/runs` | List runs for workflow |
| POST | `/api/workflows/{id}/cancel` | Cancel latest run |
| GET | `/api/workflows/runs/{run_id}` | Get run details |
| POST | `/api/workflows/runs/{run_id}/pause` | Pause run |
| POST | `/api/workflows/runs/{run_id}/resume` | Resume run |
| POST | `/api/workflows/runs/{run_id}/cancel` | Cancel run |
| GET | `/api/workflows/runs/{run_id}/events` | Get run events |
| GET | `/api/workflows/approvals/{id}` | Get approval status |
| POST | `/api/workflows/approvals/{id}/approve` | Approve |
| POST | `/api/workflows/approvals/{id}/reject` | Reject |
| POST | `/api/workflows/webhook/{workflow_id}` | Webhook trigger |

All endpoints require `admin.workflow` permission (RBAC).

---

## 11. Database Schema

### `workflows`
| Column | Type | Description |
|--------|------|-------------|
| id | String(36) | PK |
| name | String(128) | Workflow display name |
| definition | JSON | Full JSON DSL |
| status | Enum(WorkflowStatus) | Lifecycle state |
| trigger_type | Enum(TriggerType) | Associated trigger |
| tenant_id | String(36) | Tenant isolation |
| created_by | String(128) | Creator |
| created_at / updated_at | DateTime | Audit timestamps |

### `workflow_nodes`
| Column | Type | Description |
|--------|------|-------------|
| id | String(36) | PK |
| workflow_id | FK → workflows.id | Parent workflow |
| node_type | Enum(NodeType) | trigger, agent, tool, ... |
| node_name | String(64) | Unique node name |
| config | JSON | Node-specific configuration |
| next_nodes | JSON | Edge list |
| sort_order | Integer | Display ordering |

### `workflow_executions` (was `workflow_runs` in old table — separate to avoid collision)
| Column | Type | Description |
|--------|------|-------------|
| id | String(36) | PK |
| workflow_id | FK → workflows.id | Parent workflow |
| status | Enum(WorkflowStatus) | Run state |
| trigger_type | Enum(TriggerType) | Origin trigger |
| current_node | String(64) | Current node |
| node_results | JSON | Per-node result map |
| context | JSON | Runtime variables |
| error | Text | Failure reason |
| started_at / completed_at | DateTime | Timing |
| duration_ms | Float | Execution time |
| tenant_id | String(36) | Tenant isolation |

### `workflow_events`
| Column | Type | Description |
|--------|------|-------------|
| id | String(36) | PK |
| workflow_id | FK → workflows.id | Parent workflow |
| run_id | FK → workflow_executions.id | Parent run |
| node_name | String(64) | Related node |
| event_type | String(32) | node_start, pause, approval, ... |
| event_data | JSON | Payload |
| severity | String(16) | info, warn, error |
| tenant_id | String(36) | Tenant isolation |

---

## 12. Security

- **RBAC**: All API endpoints require `admin.workflow` permission
- **Tenant Isolation**: Every query filters by `tenant_id`; cross-tenant access is prevented
- **Webhook HMAC**: `WebhookTrigger` validates HMAC-SHA256 signatures
- **Audit Trail**: All state transitions logged in `workflow_events` table

---

## 13. Testing

The test suite in `tests/workflow/` covers:

- **Parser**: 20+ validation scenarios (missing fields, duplicate names, invalid types, connectivity)
- **Nodes**: 25+ execution tests for all 6 node types (success, failure, waiting states)
- **Triggers**: 17+ tests for API, Webhook, Schedule, SyncEvent, and TriggerManager
- **Approval**: 17+ tests for create, approve, reject, timeout, callbacks
- **Engine**: 30+ tests for CRUD, execution lifecycle, pause/resume/cancel, tenant isolation
- **API**: 15+ endpoint tests for all routes
- **Observability**: 7 smoke tests ensuring no crashes
- **Models**: 14+ persistence tests for all ORM models

Total: ~145 tests

---

## 14. Upgrading from Phase 8

The project version is updated to `v0.10.0` and description reflects "Enterprise AI Automation Platform".

Run the migration:
```bash
alembic upgrade head
```

All existing tests (1000+) must continue to pass after applying Phase 9 changes.