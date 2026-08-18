# Enterprise AI Agent Platform · 企业级 AI Agent 平台

> **这不是一个聊天机器人。**  
> 这是一个面向企业的 AI 自动化平台 —— 融合知识管理、智能 Agent 运行时、可视化工作流编排与可观测运维体系，专为 DevOps 与知识密集型业务场景设计。

---

## 一、项目定位 / Project Positioning

### 核心定位

企业级 AI Agent 基础设施平台，旨在帮助组织将碎片化的业务知识、API 工具与 AI 推理能力整合为可编排、可管控、可观测的智能自动化流水线。

### 适用场景

| 场景 | 说明 |
|------|------|
| **智能知识库 / RAG** | 对内部文档、代码库、运维手册进行语义检索与智能问答 |
| **DevOps 自动化** | 故障排查、日志分析、变更影响评估、CI/CD 决策辅助 |
| **业务流程编排** | 将 AI Agent 接入审批、工单、监控告警等既有业务流程 |
| **MCP Agent 生态** | 通过 Model Context Protocol 集成第三方工具与服务 |

### 设计原则

- **可集成** —— 不为替代现有系统，而为增强它们
- **可观测** —— 全链路追踪、度量与日志，拒绝黑盒
- **可管控** —— 细粒度 RBAC、多租户隔离、操作审计
- **可演进** —— 模块化架构，每个组件可独立替换或扩缩

---

## 二、核心能力 / Core Capabilities

### 1. 知识管理 & RAG 引擎

- 多格式文档解析（Markdown、PDF、Word、代码文件）
- 基于 ChromaDB 的向量化存储与语义检索
- 混合检索策略（关键词 + 向量 + 重排序）
- 知识库版本管理与自动同步
- 文档切片策略可配置（按标题、按语义、按 Token 窗口）

### 2. AI Agent 运行时

- 基于 FastAPI 的轻量级 Agent 执行引擎
- 支持多种 LLM 后端（OpenAI / Claude / 本地模型）
- 工具调用（Function Calling）与 MCP 协议集成
- Agent 记忆管理（会话级 + 持久化）
- 链式与并行 Agent 编排

### 3. 工作流自动化

- 可视化 DAG 工作流编辑器（React + React Flow）
- 支持条件分支、循环、子工作流、人工审批节点
- 定时触发与 Webhook 触发
- 内置 DevOps 工具节点（Git、Docker、Kubernetes、SSH）

### 4. MCP 集成

- 原生支持 Model Context Protocol 规范
- MCP 工具注册中心与动态发现
- 第三方 MCP Server 接入网关
- 工具调用权限策略与速率限制

### 5. 企业级安全

- **RBAC** —— 基于角色的访问控制，支持自定义角色
- **多租户** —— 租户级隔离（数据、配置、资源配额）
- **审计日志** —— 所有操作全量记录，支持回溯与告警
- **密钥管理** —— API Key、数据库密码等敏感信息加密存储

### 6. 可观测性

- **链路追踪** —— OpenTelemetry 分布式追踪
- **指标监控** —— Prometheus 指标暴露 + Grafana 仪表盘
- **日志聚合** —— 结构化日志输出，兼容 ELK / Loki
- **健康检查** —— 组件级 / 服务级 / 依赖级健康探测

### 7. 部署与运维

- **Docker Compose** —— 一键本地部署
- **Kubernetes** —— Helm Chart 生产级部署
- **水平扩缩** —— Agent 运行时无状态设计，支持自动伸缩
- **配置中心** —— 集中化配置管理，运行时热更新

---

## 三、技术亮点 / Technical Highlights

### 架构设计

- **前后端分离**：Python FastAPI 后端 + React TypeScript 前端
- **事件驱动**：基于 PostgreSQL LISTEN/NOTIFY 与 Redis Pub/Sub 实现异步事件总线
- **插件化工具系统**：Agent Tool 采用注册制，支持动态加载
- **统一向量层**：ChromaDB 作为默认向量数据库，抽象接口可切换 Milvus / Qdrant

### 性能优化

- 文档解析与向量化采用异步任务队列（Celery + Redis）
- RAG 检索引入缓存分层（本地 LRU + Redis 分布式缓存）
- Agent 执行上下文复用，减少 LLM 重复调用
- 前端代码分割 + React Router 懒加载

### 工程实践

- **完整类型系统**：Python Pydantic v2 + TypeScript 严格模式
- **自动化测试**：单元测试（pytest）+ 集成测试 + E2E 测试
- **CI/CD 流水线**：GitHub Actions 自动化构建、测试、容器镜像发布
- **代码质量**：Ruff（Python  lint）、ESLint + Prettier（TypeScript）

---

## 四、竞品对比 / Comparison with Similar Products

| 维度 | Enterprise AI Agent Platform | Dify | n8n | LangGraph |
|------|------------------------------|------|-----|-----------|
| **定位** | 企业级 AI 自动化平台 | LLM 应用开发平台 | 通用工作流自动化 | LLM 编排框架 |
| **RAG 引擎** | 内置（ChromaDB，可切换） | 内置 | ❌ 需自建 | ❌ 需自建 |
| **工作流编排** | DAG + 条件 + 人工审批 | 简单链式 | 丰富 DAG | 图编排（代码级） |
| **MCP 协议** | 原生支持 | ❌ | ❌ | 有限支持 |
| **多租户** | ✅ 原生支持 | ❌ 社区版不支持 | ❌ 需自建 | ❌ |
| **RBAC** | ✅ 细粒度 | ❌ 社区版不支持 | ✅ 部分 | ❌ |
| **审计日志** | ✅ 全量操作审计 | ❌ | ✅ 企业版 | ❌ |
| **可观测性** | OpenTelemetry + Prometheus + Grafana | 基础日志 | 基础日志 | 基础日志 |
| **部署方式** | Docker / K8s / Helm | Docker / K8s | Docker / K8s | 库依赖 |
| **DevOps 深度** | 内置 Git/Docker/K8s/SSH 工具 | ❌ | 社区节点 | ❌ |
| **开源协议** | Apache 2.0 | Apache 2.0 | Sustainable Use License | MIT |

### 选择建议

- 如果只需要 **LLM 应用快速原型** → Dify
- 如果需要 **通用业务流程自动化** → n8n
- 如果要做 **LLM 底层编排研究** → LangGraph
- 如果需要 **企业级 AI 自动化 + 知识管理 + 可观测运维** → **本平台**

---

## 五、架构简述 / Architecture Brief

```
┌─────────────────────────────────────────────────────────────┐
│                       Presentation Layer                     │
│  React SPA (TypeScript) · React Router · Tailwind CSS       │
│  React Flow (Workflow Editor) · Monaco Editor (Code View)   │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP / WebSocket
┌───────────────────────────▼─────────────────────────────────┐
│                      Gateway Layer                           │
│  FastAPI · JWT Auth · Rate Limiter · Request Validation     │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Service Layer (Core)                      │
│  ┌──────────┐ ┌──────────────┐ ┌──────────────────────────┐ │
│  │  Agent   │ │  Knowledge   │ │  Workflow Engine          │ │
│  │ Runtime  │ │  Manager     │ │  (DAG Executor)           │ │
│  │ ──────── │ │ ──────────── │ │ ────────────────────────  │ │
│  │ LLM Call │ │ Doc Parser   │ │ Node Scheduler            │ │
│  │ Tool Sys │ │ Vector Store │ │ Condition Router          │ │
│  │ Memory   │ │ Retriever    │ │ Human-in-the-Loop         │ │
│  │ MCP Gate │ │ Reranker     │ │ Webhook / Timer Trigger   │ │
│  └──────────┘ └──────────────┘ └──────────────────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Infrastructure Layer                      │
│  PostgreSQL  ·  Redis  ·  ChromaDB  ·  Celery + RabbitMQ    │
│  OpenTelemetry Collector · Prometheus · Grafana · Loki      │
│  Docker · Kubernetes · Helm                                 │
└─────────────────────────────────────────────────────────────┘
```

### 关键数据流

1. **知识注入**：文档 → 解析器 → 切片器 → Embedding → ChromaDB
2. **RAG 问答**：用户问题 → 检索器（关键词 + 向量）→ 重排序 → LLM 上下文合成 → 回答
3. **Agent 执行**：触发事件 → 工作流引擎解析 DAG → 依次/并行执行 Agent 节点 → 工具调用 → 结果聚合
4. **运维观测**：服务 → OpenTelemetry SDK → Collector → Prometheus（指标）+ Loki（日志）→ Grafana

---

## 六、技术栈 / Technology Stack

| 层 | 技术 |
|----|------|
| **后端** | Python 3.11+ · FastAPI · SQLAlchemy · Alembic · Celery |
| **前端** | React 18 · TypeScript · React Router · Tailwind CSS · React Flow |
| **数据库** | PostgreSQL 15 · Redis 7 · ChromaDB |
| **LLM** | OpenAI API · Claude API · 兼容 OpenAI 协议的本地模型 |
| **可观测** | OpenTelemetry · Prometheus · Grafana · Loki |
| **部署** | Docker · Docker Compose · Kubernetes · Helm 3 |
| **CI/CD** | GitHub Actions · Docker Registry · 自动化测试 |
| **安全** | JWT · OAuth2 · RBAC · 多租户 · 审计日志 · 字段级加密 |

---

## 七、项目状态 / Project Status

- **当前阶段**：核心功能开发完成，企业级特性逐步交付中
- **开发周期**：12 周（MVP 4 周 + 企业特性 8 周）
- **覆盖场景**：知识库问答、Agent 工作流编排、多云资源纳管

---

*Enterprise AI Agent Platform — 将知识转化为自动化，将自动化转化为生产力。*