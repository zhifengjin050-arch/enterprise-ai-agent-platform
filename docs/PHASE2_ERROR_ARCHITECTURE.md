# Phase 2: 统一企业级异常体系 — 架构文档

> **日期**: 2026-08-18
>
> **版本**: v0.7.0
>
> **状态**: 完成 ✅

---

## 目录

1. [异常体系设计](#1-异常体系设计)
2. [API 响应规范](#2-api-响应规范)
3. [全局异常处理器](#3-全局异常处理器)
4. [Request ID 中间件](#4-request-id-中间件)
5. [结构化日志体系](#5-结构化日志体系)
6. [使用方式](#6-使用方式)
7. [迁移情况](#7-迁移情况)
8. [遗留问题](#8-遗留问题)

---

## 1. 异常体系设计

### 1.1 目录结构

```
app/core/exceptions/
├── __init__.py          # 导出所有异常类
├── base.py              # BaseAppException
├── database.py          # DatabaseException 及其子类
├── connector.py         # ConnectorException 及其子类
├── auth.py              # AuthException 及其子类
├── permission.py        # PermissionException 及其子类
├── validation.py        # ValidationException 及其子类
└── external.py          # ExternalServiceException 及其子类
```

### 1.2 异常层次

```
Exception
└── BaseAppException
    ├── DatabaseException (500)
    │   ├── DatabaseConnectionError (503)
    │   ├── DatabaseQueryError (500)
    │   └── DatabaseIntegrityError (409)
    ├── ConnectorException (500)
    │   ├── ConnectorConfigError (400)
    │   ├── ConnectorAuthException (401)
    │   ├── ConnectorConnectionException (502)
    │   └── ConnectorSyncException (500)
    ├── AuthException (401)
    │   ├── InvalidToken (401)
    │   └── TokenExpired (401)
    ├── PermissionException (403)
    │   └── PermissionDenied (403)
    ├── ValidationException (422)
    │   └── InvalidParameter (422)
    └── ExternalServiceException (502)
        └── ThirdPartyAPIError (502)
```

### 1.3 BaseAppException 设计

```python
class BaseAppException(Exception):
    code: str          # 机器可读错误码, e.g., "CONNECTOR_AUTH_FAILED"
    message: str       # 人类可读描述
    http_status: int   # HTTP 状态码
    details: dict      # 附加结构化上下文

    def __init__(self, *, message=None, details=None):
        ...

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }
```

### 1.4 错误码规范

| 错误码 | HTTP | 说明 |
|--------|------|------|
| `INTERNAL_ERROR` | 500 | 未预期的内部错误 |
| `DATABASE_ERROR` | 500 | 数据库通用错误 |
| `DATABASE_CONNECTION_ERROR` | 503 | 数据库连接失败 |
| `DATABASE_QUERY_ERROR` | 500 | 查询运行时错误 |
| `DATABASE_CONSTRAINT_ERROR` | 409 | 约束违反（唯一/外键等） |
| `CONNECTOR_ERROR` | 500 | 连接器通用错误 |
| `CONNECTOR_CONFIG_ERROR` | 400 | 连接器配置无效 |
| `CONNECTOR_AUTH_FAILED` | 401 | 连接器认证失败 |
| `CONNECTOR_CONNECTION_ERROR` | 502 | 连接外部源失败 |
| `CONNECTOR_SYNC_ERROR` | 500 | 同步操作失败 |
| `AUTH_ERROR` | 401 | 认证通用错误 |
| `AUTH_INVALID_TOKEN` | 401 | Token 无效 |
| `AUTH_TOKEN_EXPIRED` | 401 | Token 过期 |
| `PERMISSION_ERROR` | 403 | 权限通用错误 |
| `PERMISSION_DENIED` | 403 | 无权限执行操作 |
| `VALIDATION_ERROR` | 422 | 校验通用错误 |
| `VALIDATION_INVALID_PARAMETER` | 422 | 参数无效 |
| `EXTERNAL_SERVICE_ERROR` | 502 | 外部服务通用错误 |
| `EXTERNAL_API_ERROR` | 502 | 第三方 API 错误 |

---

## 2. API 响应规范

### 2.1 成功响应

```json
{
    "success": true,
    "data": { ... }
}
```

### 2.2 错误响应

```json
{
    "success": false,
    "error": {
        "code": "CONNECTOR_AUTH_FAILED",
        "message": "Connector authentication failed",
        "details": {
            "source": "Feishu"
        }
    },
    "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### 2.3 辅助函数

```python
from app.core.response import success_response, error_response

# 成功响应
return success_response(data={"key": "value"})

# 错误响应
return error_response(
    code="CONNECTOR_AUTH_FAILED",
    message="Connector authentication failed",
    details={"source": "Feishu"},
    request_id=request.state.request_id,
)
```

### 2.4 Pydantic 模型

```python
class SuccessResponse(BaseModel, Generic[DataT]):
    success: bool = True
    data: DataT

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}

class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
    request_id: str = ""
```

---

## 3. 全局异常处理器

### 3.1 注册方式

在 `app/main.py` 中自动注册：

```python
from app.core.exception_handlers import register_exception_handlers

app = FastAPI(...)
register_exception_handlers(app)
```

### 3.2 处理器链

| 处理器 | 捕获类型 | HTTP 状态码 |
|--------|---------|------------|
| `base_app_exception_handler` | `BaseAppException` 及其所有子类 | 异常自带 |
| `validation_exception_handler` | `RequestValidationError` | 422 |
| `sqlalchemy_exception_handler` | `IntegrityError` / `OperationalError` / `TimeoutError` | 409/503/503 |
| `generic_exception_handler` | 所有未处理 `Exception` | 500 |

### 3.3 安全设计

- SQLAlchemy 异常处理器 **隐藏** 底层数据库细节（不会暴露约束名、SQL 语句等）
- 所有未捕获异常被通用处理器转为统一的 `INTERNAL_ERROR` 响应
- 完整的异常堆栈写入日志（`exc_info=True`），但不返回给客户端

---

## 4. Request ID 中间件

### 4.1 文件位置

`app/core/middleware/request_id.py`

### 4.2 功能

- 为每个请求生成 UUID v4
- 通过 `request.state.request_id` 在端点中访问
- 在响应头中设置 `X-Request-ID`
- 在结构化日志中自动注入 `request_id`

### 4.3 注册方式

已在 `app/main.py` 中注册：

```python
from app.core.middleware.request_id import RequestIDMiddleware
app.add_middleware(RequestIDMiddleware)
```

---

## 5. 结构化日志体系

### 5.1 目录结构

```
app/core/logging/
├── __init__.py    # 导出 configure_logging, get_logger
├── config.py      # 配置根日志器
└── formatter.py   # JSON 格式器
```

### 5.2 使用方法

```python
from app.core.logging import configure_logging, get_logger

# 在应用启动时配置一次
configure_logging(level="INFO", json_format=True)

# 在每个模块中使用
logger = get_logger(__name__)
logger.info("Service started", extra={"version": "1.0"})
logger.warning("Error occurred", extra={"request_id": "abc-123"})
```

### 5.3 日志格式

```json
{
    "time": "2026-08-18T12:00:00.000Z",
    "level": "INFO",
    "module": "app.api.connector",
    "message": "Connector sync completed",
    "request_id": "abc-123",
    "user_id": "user-456",
    "extra": {
        "connector_id": "feishu-1",
        "documents_count": 42
    },
    "exception": ["Traceback (most recent call last):..."]
}
```

### 5.4 配置项

已在 `app/core/config.py` 中新增：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `log_level` | `"INFO"` | 日志级别 |
| `log_json_format` | `True` | 是否使用 JSON 格式 |

---

## 6. 使用方式

### 6.1 抛出异常

```python
# 新代码推荐方式
from app.core.exceptions import ConnectorAuthException

raise ConnectorAuthException(
    message="Feishu token expired",
    details={"source": "Feishu", "connector_id": "feishu-1"},
)
```

```python
# 旧代码兼容方式（自动转换）
from app.connector.exceptions import AuthenticationError

raise AuthenticationError(source="Feishu", detail="invalid token")
```

### 6.2 在 API 端点中

```python
from app.core.exceptions import InvalidParameter
from app.core.response import success_response

@router.get("/items/{item_id}")
async def get_item(item_id: str, request: Request):
    if not item_id:
        raise InvalidParameter(details={"field": "item_id"})
    # ...
    return success_response(data={"id": item_id, "name": "Item"})
```

### 6.3 捕获并转换

```python
from app.core.exceptions import DatabaseIntegrityError
from sqlalchemy.exc import IntegrityError

try:
    await session.commit()
except IntegrityError as exc:
    await session.rollback()
    raise DatabaseIntegrityError(
        message="Document with this name already exists",
        details={"title": doc.title},
    ) from exc
```

---

## 7. 迁移情况

### 7.1 向后兼容性

所有旧异常类保持可用：

| 旧异常 | 新继承链 | 状态 | 说明 |
|--------|---------|------|------|
| `ConnectorError` | → `BaseAppException` | ✅ 完全兼容 | `http_status=500`, `code="CONNECTOR_ERROR"` |
| `ConnectionError` | → `ConnectorError` → `BaseAppException` | ✅ 完全兼容 | `.source` 属性通过 property 保留 |
| `AuthenticationError` | → `ConnectorError` → `BaseAppException` | ✅ 完全兼容 | `.source` 属性通过 property 保留 |
| `NotFoundError` | → `ConnectorError` → `BaseAppException` | ✅ 完全兼容 | `.resource`, `.source` 属性保留 |
| `SyncError` | → `ConnectorError` → `BaseAppException` | ✅ 完全兼容 | `.source` 属性保留 |
| `EmbeddingError` | → `ExternalServiceException` → `BaseAppException` | ✅ 完全兼容 | |

### 7.2 已修复的运行时 Bug

| Bug | 位置 | 修复内容 |
|-----|------|---------|
| `import_document` 导入不存在的函数 | `app/document/importer.py:100` | 改为使用 `WorkflowOrchestrator.process_document()` |
| `import_document` 是同步但应 async | `app/document/importer.py:32` | 改为 `async def import_document()` |
| 测试未 await | `tests/test_document/test_converter.py:45` | 改为 `await importer.import_document()` |

### 7.3 已修复的静默异常

| 文件 | 修改内容 |
|------|---------|
| `app/entity/extractor.py:162` | `except Exception: pass` → `except Exception as exc: logger.warning(...)` |
| `app/relation/extractor.py:200` | 同上 |
| `app/query/rewrite.py:172` | 同上 |
| `app/agent/knowledge_agent.py:154` | `except Exception: pass` → `except Exception as exc: logger.warning(...)` |
| `app/graph/builder.py:91,111` | 同上 |
| `app/search/indexer.py:109,156,186,199` | 同上 |
| `app/search/fulltext.py:73,155` | 同上 |

### 7.4 新增日志模块

| 文件 | logger |
|------|--------|
| `app/entity/extractor.py` | `logging.getLogger(__name__)` |
| `app/relation/extractor.py` | `logging.getLogger(__name__)` |
| `app/query/rewrite.py` | `logging.getLogger(__name__)` |
| `app/agent/knowledge_agent.py` | `logging.getLogger(__name__)` |
| `app/graph/builder.py` | `logging.getLogger(__name__)` |
| `app/search/indexer.py` | `logging.getLogger(__name__)` |
| `app/search/fulltext.py` | `logging.getLogger(__name__)` |

---

## 8. 遗留问题

| 问题 | 原因 | 计划修复阶段 |
|------|------|-------------|
| 57% API 端点仍无认证保护 | Phase 2 专注于错误体系构建，不涉及认证 | Phase 7 |
| 约 130 个模块仍无 `logging.getLogger(__name__)` | Phase 2 仅修复了修改触及的模块 | Phase 8/10 |
| `app/main.py` 中仍有 `print()` 被替换为 `logger.info()` | ✅ **已修复** | — |
| `app/embedding/exceptions.py` 中的 `ConnectionError` 名遮蔽 | 继承自 `ExternalServiceException`，不影响功能 | Phase 3 |
| `issubclass(ConnectionError, ConnectorError)` 不再是 True | 因 `ConnectionError` 直继承 `ConnectorError`，不影响功能 | — |
| 统一 Response Schema（`success_response`）尚未在所有 API 端点中采用 | 第二阶段重点在基础设施 | Phase 7 |
| Ruff/mypy 尚未配置 | 工具链将在 Phase 10 安装 | Phase 10 |

---

*文档生成于 2026-08-18 | 对应 Phase 2 完整实施*