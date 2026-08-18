---
title: 企业 API 开发规范
doc_type: ARCHITECTURE
tags: [api, development, rest, design]
version: 3.0
author: Platform Team
---

# 企业 API 开发规范

## 1. API 设计原则

### 1.1 RESTful 规范
- 资源命名使用复数名词: `/api/users`, `/api/orders`
- 使用 HTTP 方法表示操作: GET/POST/PUT/DELETE
- 版本号放在路径中: `/api/v1/users`
- 分页参数: `limit`, `offset`, `page`

### 1.2 响应格式
```json
{
  "success": true,
  "data": {},
  "error": null,
  "meta": {
    "page": 1,
    "limit": 20,
    "total": 100
  }
}
```

### 1.3 错误响应
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数校验失败",
    "details": [
      {"field": "email", "message": "无效的邮箱格式"}
    ]
  }
}
```

## 2. 认证与授权

### 2.1 认证方式
- JWT Token: `Authorization: Bearer <token>`
- API Key: `X-API-Key: <key>`
- Token 有效期: 24小时
- Refresh Token: 7天

### 2.2 权限控制
- 基于 RBAC 的权限模型
- 每个 API 端点标注所需权限
- 租户间数据完全隔离

## 3. API 网关配置

### 3.1 限流策略
- 普通用户: 100 请求/分钟
- VIP 用户: 1000 请求/分钟
- 内部服务: 不限制

### 3.2 超时配置
- 普通 API: 30s
- 文件上传: 5min
- 流式 API: 无超时

## 4. 文档与测试

### 4.1 文档要求
- 使用 OpenAPI 3.0 规范
- 每个端点必须有描述和示例
- 所有请求/响应必须有 schema

### 4.2 测试要求
- 单元测试覆盖率 > 80%
- 集成测试覆盖所有关键路径
- 性能测试 QPS > 1000