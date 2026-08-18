# Enterprise Security & Multi-Tenant SaaS Architecture

## 概述

Phase 7 将平台升级为企业 SaaS 安全基础：**TenantContext + JWT Refresh + RBAC + API Key + Audit + Quota**，
在不破坏 Connector / SyncEngine / Knowledge Intelligence / Agent Runtime 的前提下增量增强。

```
                 User
                  |
             Auth Gateway
                  |
          Tenant Context
                  |
        +---------+---------+
        |
       RBAC
        |
   Enterprise APIs
        |
 +------+------+------+
 |             |
Agent       Knowledge
 |             |
LLM         RAG
 |
Tools
```

---

## 风险审计摘要（实施前）

| 风险 | 状态 |
|------|------|
| 多数业务 API 无鉴权 | 本阶段为 security 管理 API + Agent 增强；业务 API 逐步挂权限 |
| Legacy `/api/agent` 开放 | 保留兼容；生产应走 `/api/agents` + RBAC |
| tenant_id 有字段无过滤 | 已加 `apply_tenant_filter` + Document/Connector list 自动过滤 |
| 开放注册可绑任意 tenant | **已修复**：`/api/auth/register` 忽略客户端 `tenant_id` |
| 无 refresh / API Key / Audit / Quota | **已补齐** |

---

## 认证流程

1. `POST /api/auth/register` — 创建用户（不接受任意 tenant_id）
2. `POST /api/auth/login` — 返回 `access_token` + `refresh_token`
3. `POST /api/auth/refresh` — 刷新令牌对
4. `GET /api/auth/me` — 当前用户

Access token：`type=access`，默认 1h  
Refresh token：`type=refresh`，默认 14d  

中间件链：`SecurityMiddleware` → `RequestIDMiddleware` → `TenantMiddleware`

`TenantMiddleware` 解析：

1. `Authorization: Bearer <jwt>`
2. `X-API-Key` / `Authorization: ApiKey <key>`
3. 匿名空上下文

---

## RBAC 模型

复用 `users` / `roles` / `permissions` / `user_roles` / `role_permissions`。

新增 `PermissionChecker.require("agent.execute")`。

权限码（节选）：

- `connector.read|write|sync`
- `knowledge.read|write|delete`
- `agent.read|write|execute`
- `admin.manage` / `admin.users` / `admin.tenant`
- `audit.read` / `quota.read` / `apikey.manage`

`admin.manage` 在 PermissionChecker 中视为超级权限。

---

## 租户隔离

### TenantContext

```python
TenantContext(tenant_id, user_id, organization_id, roles, auth_method)
```

contextvars 注入，请求结束清理。

### 数据隔离

`app/tenant/isolation.py`：

- `apply_tenant_filter(stmt, column, tenant_id=None)`
- `assert_tenant_owns(resource_tenant_id)`
- 无上下文时保持兼容（不强制过滤，便于测试/迁移）

已增强：

- `KnowledgeRepository.list_documents` — 上下文自动 filter
- `ConnectorConfigRepository.list` — 同上
- `Agent` list API — 优先当前用户 tenant

### Organization

表 `organizations`：enterprise / department / team，树形 `parent_id`。  
`users.organization_id` 可选 FK。

---

## API Key 设计

表 `api_keys`：`id, tenant_id, name, key_prefix, key_hash, status, last_used_at, expires_at`

- 明文仅创建/轮转时返回一次：`ek_<prefix>_<secret>`
- `create` / `revoke` / `rotate` / `authenticate`
- API：`/api/api-keys`

---

## 审计设计

表 `audit_logs`：user / tenant / action / resource / ip / timestamp

敏感动作示例：`auth.login`、`api_key.*`、`agent.execute`、`connector.sync`、`document.delete`

API：`GET /api/audit/logs`

---

## 配额设计

表 `quotas`（每租户一行）：

| Plan | tokens/day | agent runs/day |
|------|------------|----------------|
| free | 1000 | 50 |
| pro | 100000 | 1000 |
| enterprise | unlimited | unlimited |

- Agent 执行前 `consume_agent_run`
- LLM Gateway `chat()` 在有 session + tenant 时 `check_tokens` / `consume_tokens`
- API：`GET /api/quota/status`、`POST /api/quota/plan`

---

## Migration

`0009_enterprise_security`：

- 新建：`organizations`、`api_keys`、`audit_logs`、`quotas`
- 补列：`users.organization_id`、`agent_tasks.user_id`
- 多表补 `tenant_id`：chunks / categories / tags / sync_* / sop / incident / task / llm_cost

---

## API 一览

| Method | Path |
|--------|------|
| POST | `/api/auth/login` `/register` `/refresh` |
| GET | `/api/users` `/api/roles` `/api/permissions` |
| POST/GET | `/api/organizations` |
| POST/GET | `/api/api-keys` + `/{id}/revoke` `/rotate` |
| GET | `/api/audit/logs` |
| GET/POST | `/api/quota/status` `/api/quota/plan` |

---

## 测试

```bash
pytest tests/security/ -q
python -m compileall app/tenant app/api_key app/audit app/quota app/auth app/api/security.py
```
