# Enterprise Connector Framework

## 概述

Enterprise Connector Framework 是企业级 DevOps RAG 知识库 Agent 的插件化连接器系统，参考 Airbyte Connector Architecture、Kubernetes Controller Pattern 和 Backstage Plugin System 设计。

连接器框架的核心目标是：

- **插件化**：每个外部数据源是一个独立插件，通过 Registry 动态注册
- **生命周期管理**：状态机管理连接器的完整生命周期
- **可观测性**：健康检查 API、结构化日志、指标收集
- **配置验证**：Pydantic Schema 驱动，启动前强制验证
- **错误恢复**：智能重试策略，区分可重试/不可重试错误

---

## 1. 如何开发新 Connector

### 1.1 创建 Connector 类

```python
from typing import Any, Dict, List, Optional
from app.connector.base import BaseConnector, ConnectorDocument
from app.connector.capability import ConnectorCapability

class MyCustomConnector(BaseConnector):
    # ── 必需类属性 ──
    name: str = "MyCustom"                       # 人类可读名称
    connector_type: str = "my_custom"            # 注册类型键（唯一）

    # ── 可选类属性 ──
    version: str = "1.0.0"                       # 语义化版本
    author: str = "Your Name"                    # 维护者
    description: str = "My custom data source"   # 简短描述
    capabilities: List[ConnectorCapability] = [  # 声明的能力
        ConnectorCapability.DOCUMENT_READ,
        ConnectorCapability.FULL_SYNC,
    ]
    features: List[str] = ["document", "custom"]

    # ── 必需抽象方法 ──
    async def test_connection(self) -> bool:
        """测试与外部源的连接"""
        ...

    async def fetch_documents(self) -> List[ConnectorDocument]:
        """获取文档列表（仅元数据）"""
        ...

    async def get_document(self, document_id: str) -> Optional[ConnectorDocument]:
        """获取单个文档（含完整内容）"""
        ...

    async def sync(
        self,
        sync_mode: str = "full",
        cursor: Optional[str] = None,
    ) -> List[ConnectorDocument]:
        """执行同步（全量或增量）"""
        ...
```

### 1.2 注册到 Registry

在 `app/connector/__init__.py` 中添加：

```python
from app.connector.my_custom import MyCustomConnector
connector_registry.register("my_custom", MyCustomConnector)
```

然后从 `__all__` 中导出。

### 1.3 可选：创建 Config Schema

```python
from pydantic import BaseModel, Field

class MyCustomConfig(BaseModel):
    api_key: str = Field(..., min_length=1, description="API Key")
    base_url: str = Field("https://default.url", description="Base URL")

# 注册到 CONNECTOR_CONFIG_SCHEMAS
from app.connector.config_schemas import CONNECTOR_CONFIG_SCHEMAS
CONNECTOR_CONFIG_SCHEMAS["my_custom"] = MyCustomConfig
```

---

## 2. 生命周期

所有连接器实例遵循严格的状态机模型：

```
REGISTERED → INITIALIZING → READY → RUNNING → READY
    ↓                            ↓         ↓
 DISABLED                    DESTROYED   FAILED → INITIALIZING
    ↓
 DESTROYED
```

### 2.1 状态定义

| 状态 | 含义 |
|------|------|
| `REGISTERED` | 类已注册但未实例化 |
| `INITIALIZING` | 正在初始化（HTTP 客户端、认证等） |
| `READY` | 初始化完成，等待同步 |
| `RUNNING` | 正在执行同步操作 |
| `FAILED` | 发生不可恢复错误 |
| `DISABLED` | 被管理员禁用 |
| `DESTROYED` | 已销毁，资源已释放 |

### 2.2 使用 LifecycleManager

```python
from app.connector.lifecycle import lifecycle_manager

# 初始化（REGISTERED → INITIALIZING → READY）
await lifecycle_manager.initialize("connector-id", connector_instance)

# 启动同步（READY → RUNNING）
await lifecycle_manager.start("connector-id")

# 停止同步（RUNNING → READY）
await lifecycle_manager.stop("connector-id")

# 标记失败（可自行恢复）
await lifecycle_manager.fail("connector-id")

# 销毁并释放资源
await lifecycle_manager.destroy("connector-id")

# 重启（DESTROYED → INITIALIZING → READY）
await lifecycle_manager.restart("connector-id")
```

所有状态变更都会记录结构化日志。

---

## 3. 配置规范

### 3.1 内置 Schema

| Connector | Schema | 必需字段 |
|-----------|--------|---------|
| Feishu | `FeishuConfig` | `app_id`, `app_secret` |
| Yuque | `YuqueConfig` | `token` |
| GitLab | `GitLabConfig` | `url`, `token`, `project_id` |

### 3.2 验证函数

```python
from app.connector.config_schemas import validate_connector_config

# 验证配置，如果无效抛出 ConnectorConfigError
validated = validate_connector_config("feishu", {
    "app_id": "cli_xxx",
    "app_secret": "secret_key",
})
```

### 3.3 自定义配置

对于无 Schema 注册的连接器类型，`validate_connector_config` 会直接返回原配置（透传）。

---

## 4. 异常处理

### 4.1 异常层次

```
BaseAppException
├── ConnectorException (500 CONNECTOR_ERROR)
│   ├── ConnectorConfigError (400 CONNECTOR_CONFIG_ERROR)
│   ├── ConnectorAuthException (401 CONNECTOR_AUTH_FAILED)
│   ├── ConnectorConnectionException (502 CONNECTOR_CONNECTION_ERROR)
│   └── ConnectorSyncException (500 CONNECTOR_SYNC_ERROR)
├── ConnectorError (500)  ← 遗留兼容
│   ├── ConnectionError (502)
│   ├── AuthenticationError (401)
│   ├── NotFoundError (500)
│   └── SyncError (500)
└── ...
```

### 4.2 重试策略

```python
from app.connector.retry import ConnectorRetryPolicy, default_retry_policy

# 使用默认策略（最多 3 次重试，指数退避）
result = await default_retry_policy.execute(
    lambda: my_connector.fetch_documents(),
    context="fetch_documents",
)

# 自定义策略
policy = ConnectorRetryPolicy(max_retries=5, backoff_base=2.0, backoff_max=60.0)
result = await policy.execute(lambda: my_api_call(), context="api_call")
```

### 4.3 错误分类

- **可重试错误**：`ConnectorConnectionException`、`TimeoutError`、`ConnectionError`、`OSError`
- **不可重试错误**：`ConnectorAuthException`、`ConnectorConfigError`

认证/配置错误永远不会重试，网络/超时错误会自动重试。

---

## 5. 测试要求

### 5.1 测试目录结构

```
tests/test_connector/
├── __init__.py
├── conftest.py                  # 共享 Fixture
├── test_base.py                 # BaseConnector 基础测试
├── test_registry.py             # 注册表测试
├── test_api.py                  # API 端点测试
├── test_feishu.py               # Feishu 连接器测试
├── test_yuque.py                # Yuque 连接器测试
├── test_gitlab.py               # GitLab 连接器测试
├── test_sync.py                 # 同步/调度器测试
├── test_models.py               # ORM 模型测试
└── framework/                   # 框架增强测试
    ├── __init__.py
    ├── test_lifecycle.py        # 生命周期测试
    ├── test_registry.py         # Registry 增强测试
    ├── test_factory.py          # Factory 模式测试
    ├── test_capability.py       # 能力系统测试
    ├── test_health.py           # 健康检查测试
    └── test_config_schema.py    # 配置 Schema 测试
```

### 5.2 覆盖率要求

- 新增框架代码覆盖率 >= 90%
- 每个 Connector 独立测试覆盖率 >= 80%
- 关键路径（sync、initialize、health_check）必须 100% 覆盖

### 5.3 测试用例设计原则

1. 每个测试只测试一个行为
2. Mock 外部 HTTP 调用
3. 测试异常路径（认证失败、网络超时、配置缺失）
4. 测试生命周期状态转换边界

---

## 6. 发布流程

### 6.1 版本号规范

遵循语义化版本（SemVer）：

- **MAJOR**: 不兼容的 API 变更（如删除抽象方法）
- **MINOR**: 向后兼容的功能新增（如新能力、新 Hook）
- **PATCH**: 向后兼容的 Bug 修复

### 6.2 发布 Checklist

1. [ ] 更新 `version` 类属性
2. [ ] 更新 CHANGELOG
3. [ ] 运行完整测试套件：`python -m pytest tests/test_connector/ -q`
4. [ ] 验证所有现有 Connector 兼容性：`python -m pytest tests/ -x -q`
5. [ ] 确认没有 import 警告：`python -W all -c "from app.connector import *"`
6. [ ] 生成/更新文档

### 6.3 向后兼容承诺

- 不删除或改名 `BaseConnector` 的抽象方法
- 不删除 `ConnectorRegistry.register()` 等公共方法
- 新方法必须提供默认实现（不强制现有子类实现）

---

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                     API Layer                            │
│  GET /api/connectors/{id}/health    (Phase 3.7)         │
│  GET /api/connectors/types/metadata (Phase 3.5)         │
│  GET /api/connectors/types/discover (Phase 3.5)         │
│  GET /api/connectors/{id}/state     (Phase 3.2)         │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                  ConnectorFactory                        │
│            (create + lifecycle initialize)                │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              ConnectorRegistry                           │
│  register / create / get_metadata / discover             │
│  list_capabilities / check_support                       │
└──────┬──────────────────────────────────┬───────────────┘
       │                                  │
┌──────▼──────────────┐    ┌──────────────▼──────────────┐
│  Connector          │    │  ConnectorLifecycleManager  │
│  Lifecycle Hooks:   │    │  State Machine              │
│  initialize()       │    │  REGISTERED → READY → ...   │
│  validate_config()  │    └─────────────────────────────┘
│  health_check()     │
│  cleanup()          │    ┌─────────────────────────────┐
└─────────────────────┘    │  RetryPolicy                │
                           │  max_retries / backoff      │
┌─────────────────────┐    │  is_retryable()             │
│  FeishuConnector    │    └─────────────────────────────┘
│  YuqueConnector     │
│  GitLabConnector    │    ┌─────────────────────────────┐
│  (Your Connector)   │    │  Config Schemas             │
└─────────────────────┘    │  FeishuConfig / YuqueConfig │
                           │  GitLabConfig               │
                           └─────────────────────────────┘
```

---

## 快速参考

### 常用 Imports

```python
# 创建连接器
from app.connector.factory import connector_factory
instance = await connector_factory.create("feishu", config={...})

# 生命周期管理
from app.connector.lifecycle import lifecycle_manager, ConnectorState
state = lifecycle_manager.get_state("connector-id")

# 注册表查询
from app.connector.registry import connector_registry
meta = connector_registry.get_metadata("feishu")
caps = connector_registry.list_capabilities("feishu")

# 配置验证
from app.connector.config_schemas import validate_connector_config
validated = validate_connector_config("feishu", config)

# 重试
from app.connector.retry import default_retry_policy
result = await default_retry_policy.execute(lambda: instance.sync(), context="sync")
```

### Sync 模式

```python
from app.connector.sync_modes import SyncMode, SyncCursor, SyncResult

# 全量同步
docs = await connector.sync(sync_mode=SyncMode.FULL.value)

# 增量同步
docs = await connector.sync(sync_mode=SyncMode.INCREMENTAL.value, cursor="checkpoint_xyz")

# 创建检查点
cursor = SyncCursor(value="2026-08-18T00:00:00Z", mode=SyncMode.INCREMENTAL)
```