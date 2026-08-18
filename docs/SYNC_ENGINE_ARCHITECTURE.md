# Enterprise Sync Engine Architecture

## 概述

Phase 4 引入 **Enterprise Sync Engine**，将同步从「Connector 直接 sync → Pipeline」升级为可持久化、可恢复、可观测的企业级同步管道。

```
Connector
    │
 SyncJob          ← 持久化执行单元
    │
 SyncEngine       ← 编排核心
    │
 Checkpoint       ← 断点游标
    │
 SyncEvent        ← CREATE / UPDATE / DELETE
    │
 DocumentPipeline ← TaskQueue → knowledge_pipeline
```

---

## 1. 模块结构

```
app/sync_engine/
├── __init__.py
├── models.py          # SyncJob / SyncCheckpoint / SyncEventRecord ORM
├── events.py          # SyncEvent / SyncEventType (CREATE, UPDATE, DELETE)
├── checkpoint.py      # SyncCheckpointManager — 游标持久化
├── job_manager.py     # SyncJobManager — Job CRUD + 生命周期
├── sync_engine.py     # SyncEngine — 核心编排
├── worker.py          # SyncWorker — 后台异步执行
└── scheduler.py       # SyncEngineScheduler — 定时触发
```

---

## 2. 数据模型

### SyncJob

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| tenant_id | str? | 租户隔离 |
| connector_id | str | 关联 ConnectorConfig |
| sync_mode | str | `full` / `incremental` / `delta` |
| status | str | `pending` / `running` / `success` / `failed` / `cancelled` / `partial` |
| cursor | str? | 当前/恢复游标 |
| total_count | int | 发现的文档数 |
| success_count | int | 成功处理数 |
| failed_count | int | 失败数 |
| started_at | datetime? | 开始时间 |
| finished_at | datetime? | 结束时间 |
| error | str? | 失败错误信息 |

### SyncCheckpoint

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| sync_job_id | str? | 产生此 checkpoint 的 Job |
| connector_id | str | 每个 connector 唯一一条 |
| cursor | str | 不透明游标值 |
| updated_at | datetime | 最后更新时间 |

### SyncEventRecord

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| sync_job_id | str | 所属 Job |
| connector_id | str | 所属 Connector |
| event_type | str | `create` / `update` / `delete` |
| document_id | str? | 外部文档 ID |
| payload | JSON? | 事件载荷 |

---

## 3. SyncResult 契约

`BaseConnector.sync()` 返回 `SyncResult`：

```python
@dataclass
class SyncResult:
    documents: List[ConnectorDocument]
    next_cursor: Optional[str] = None   # 下一页游标
    has_more: bool = False              # 是否还有更多页
    # Phase 3 兼容
    cursor: Optional[SyncCursor] = None
    total_count: int = 0
    errors: List[str] = []
```

向后兼容：若 Connector 仍返回 `List[ConnectorDocument]`，`normalize_sync_result()` 会自动包装。

---

## 4. 增量同步与断点恢复

### 流程

1. `sync_mode=incremental` 时，SyncEngine 从 `SyncCheckpoint` 加载 cursor
2. 调用 `connector.sync(sync_mode="incremental", cursor=cursor)`
3. Connector 过滤 `updated_at <= cursor` 的文档
4. 成功后将 `next_cursor` 写入 Checkpoint 和 SyncJob
5. **失败时**：保留已有 cursor，下次从断点继续

### 示例

```python
from app.sync_engine import SyncEngine

engine = SyncEngine(session)
job = await engine.start_sync(
    connector_id="...",
    connector_type="feishu",
    config={"app_id": "...", "app_secret": "..."},
    sync_mode="incremental",
    resume=True,  # 从 checkpoint 恢复
)
```

---

## 5. SyncEvent

用于后续 Webhook / CDC / Realtime Sync：

```python
from app.sync_engine.events import SyncEvent, SyncEventType

event = SyncEvent.create("doc-123", connector_id="c1", sync_job_id="j1")
event = SyncEvent.update("doc-123", payload={"title": "Updated"})
event = SyncEvent.delete("doc-456")
```

每个文档处理时自动持久化为 `SyncEventRecord`。

---

## 6. API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/connectors/{id}/sync` | 触发同步，返回 `sync_job_id` |
| GET | `/api/sync/jobs` | 列出 SyncJob |
| GET | `/api/sync/jobs/{id}` | 查询 Job 状态 |
| GET | `/api/sync/jobs/{id}/events` | 列出 Job 事件 |

### 触发同步

```http
POST /api/connectors/{id}/sync
Content-Type: application/json

{
  "sync_mode": "incremental",
  "resume": true
}
```

响应：

```json
{
  "detail": "Sync triggered for connector '...'",
  "sync_job_id": "uuid",
  "sync_record_id": "uuid",
  "sync_mode": "incremental",
  "status": "pending"
}
```

`sync_record_id` 保留以兼容旧客户端。

---

## 7. 与旧系统的关系

| 组件 | 状态 | 说明 |
|------|------|------|
| `SyncRecord` | 保留 | 旧同步历史，API 仍写入 |
| `app/connector/scheduler.py` | 保留 | 兼容旧路径，已适配 SyncResult |
| `SyncJob` | **推荐** | 新同步执行单元 |
| `SyncEngine` / `SyncWorker` | **推荐** | 新编排与后台执行 |
| `app/sync/` | 遗留 | 与 connector 层并行的旧引擎，勿混用 |

---

## 8. 开发指南

### 在 Connector 中支持增量

```python
async def sync(self, sync_mode="full", cursor=None) -> SyncResult:
    docs = await self.fetch_documents()
    if sync_mode == "incremental" and cursor:
        docs = [d for d in docs if d.updated_at and d.updated_at > cursor]

    full = [...]  # 拉取内容
    next_cursor = max((d.updated_at for d in full if d.updated_at), default=cursor)
    return SyncResult.from_documents(full, next_cursor=next_cursor, has_more=False)
```

### 后台提交

```python
from app.sync_engine import sync_worker

job_id = await sync_worker.submit(
    connector_id="...",
    connector_type="yuque",
    config={...},
    sync_mode="incremental",
)
```

### 查询进度

```python
from app.sync_engine import SyncJobManager

mgr = SyncJobManager(session)
job = await mgr.get_job(job_id)
events = await mgr.list_events(job_id)
```

---

## 9. 异常与重试

复用 Phase 2 异常体系：

- `ConnectorConnectionException` → 可重试
- `ConnectorAuthException` / `ConnectorConfigError` → 不可重试
- `ConnectorRetryPolicy` → 指数退避 + jitter

SyncEngine 在 Job 失败时：

1. 将 status 设为 `failed`
2. 写入 `error`
3. **保留 checkpoint cursor** 供下次 resume

---

## 10. 迁移

Alembic revision: `0006_add_sync_engine_tables`

```bash
alembic upgrade head
```

创建表：`sync_jobs`、`sync_checkpoints`、`sync_events`。

---

## 11. 测试

```
tests/sync_engine/
├── conftest.py
├── test_sync_job.py          # SyncJob CRUD / 生命周期
├── test_checkpoint.py        # Checkpoint 持久化
├── test_incremental.py       # 增量同步 + SyncResult
├── test_cursor_recovery.py   # 失败后游标恢复
├── test_failure_retry.py     # 重试策略 + 部分失败
└── test_api.py               # API 端点
```

运行：

```bash
python -m pytest tests/sync_engine/ tests/test_connector/ -q
```

---

## 12. 后续建议

1. **分页增量**：利用 `has_more` 循环拉取多页
2. **Webhook 入站**：根据 SyncEvent 驱动实时同步
3. **Job 取消**：`CANCELLED` 状态 + API
4. **进度推送**：WebSocket / SSE 推送 SyncJob 进度
5. **废弃旧 SyncRecord**：迁移完成后统一到 SyncJob
