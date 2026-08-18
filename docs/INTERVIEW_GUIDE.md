# Enterprise AI Agent Platform — 面试指南

> 本文档为求职面试准备，包含多时间版本的自我介绍和关键技术深挖问答。
> 适用岗位：SRE / DevOps / AI 工程师 / 后端开发

---

## 一、自我介绍版本

### 30 秒版本（电梯演讲）

> 「我设计并实现了一个企业级 AI Agent 平台。它能把公司内部的文档、知识库和运维数据接入 AI 系统，通过 RAG 技术让 AI 理解企业知识，再通过 Agent 和工作流引擎实现自动化。整个平台支持多租户隔离、私有化部署（Docker/K8s），并且通过了 1000+ 测试用例验证。」

### 3 分钟版本（通用面试）

> 「我主导了 **Enterprise AI Agent Platform** 的设计与实现，这是一套企业级 AI 自动化基础设施。
>
> **项目背景**：传统企业面临知识分散、运维响应慢、重复劳动多的问题。需要一个平台能把企业知识（文档、代码、运维数据）统一接入，并通过 AI Agent 实现自动化的知识检索和任务执行。
>
> **我的角色**：作为项目负责人，我负责整体架构设计、核心模块开发和技术决策。团队规模 3~5 人，开发周期约 3 个月。
>
> **核心成果**：
> 1. **Hybrid RAG 引擎** — 结合 BM25 全文搜索、向量嵌入和重排序，在企业知识检索上实现高召回率
> 2. **AI Agent Runtime** — 自研 Planner + Tool System + Memory 架构，支持 ReAct 规划和动态工具调用
> 3. **Workflow 自动化引擎** — DAG 编排，支持 Trigger → Agent → Tool → Approval 的完整自动化流程
> 4. **企业级安全** — JWT 认证、RBAC、多租户隔离、全量审计日志
> 5. **云原生部署** — Docker Compose 一键部署 + Kubernetes/Helm 生产部署
>
> 技术栈：Python（FastAPI）、React（TypeScript）、PostgreSQL、Redis、ChromaDB、Docker、Kubernetes、Prometheus、OpenTelemetry。」

### 10 分钟版本（技术深挖）

在 3 分钟基础上增加：

> **架构深度**：
> 平台分六层：用户层（React Dashboard）→ 安全层（JWT/RBAC/多租户）→ Agent 运行时（Planner → Context → Retriever → Tool → LLM）→ 能力层（Knowledge、Workflow、MCP）→ 连接层（Connector Framework）→ 数据层（PostgreSQL/Redis/ChromaDB）。
>
> **关键技术细节**：
> - **Hybrid RAG**：BM25 做关键词召回 → Embedding 做语义召回 → RRF 融合 → CohereRerank 精排，三层递进确保准确率
> - **Agent Planner**：ReAct 策略让 Agent 能观察环境 → 思考 → 行动 → 循环，直到任务完成
> - **Workflow Engine**：DAG 图结构，每个节点独立执行，支持条件分支和人工审批节点
> - **MCP 协议适配**：将外部工具（K8s/Docker/DB）通过统一接口注册到 Agent Tool System
>
> **遇到的挑战**：
> 1. *多数据源同步一致性* → 设计 Cursor + Checkpoint 增量同步机制，支持断点续传
> 2. *Agent 执行可靠性* → 实现 Planner 重规划机制，失败自动降级和重试
> 3. *多租户隔离* → 在 ORM 层和 API 层双层隔离，数据级 + 请求级
> 4. *测试治理* → 1200+ 测试用例，pytest-asyncio + 内存 SQLite 保证 CI 速度

---

## 二、技术深挖问答

### Q1: 为什么设计 Sync Engine？直接用 API 调用不行吗？

> **核心原因：企业数据源的差异性**
>
> 企业数据源（飞书文档、语雀、GitLab）各有不同的 API 限频、数据结构和变更追踪方式。Sync Engine 抽象了统一的同步生命周期：
>
> 1. **增量同步**：通过 Cursor 记录同步断点，每次只同步变更部分，避免全量拉取
> 2. **断点续传**：网络中断或 API 限频时，Checkpoint 机制可以从断点恢复
> 3. **失败重试**：指数退避策略，应对 API 临时不可用
> 4. **统一抽象**：无论数据源是飞书还是 GitLab，上层 Knowledge Intelligence 看到的都是统一的数据模型
>
> 如果没有 Sync Engine，每个数据源都需要业务代码单独处理增量逻辑，维护成本会随数据源数量线性增长。

### Q2: 为什么自研 Agent Runtime，而不是直接用 LangChain / LangGraph？

> **选择自研的原因**：
>
> 1. **企业级可观测性**：我们需要每个 Agent 执行的完整 Trace 链（Planner 决策 → Tool 调用 → LLM 调用 → 结果），LangChain 的 Callback 机制不足以满足我们的审计和监控要求
> 2. **Tool 系统灵活性**：企业场景需要 Tool 能动态注册和发现（通过 MCP 协议），LangChain 的 Tool 加载是静态的
> 3. **多租户安全**：每个 Tool 调用需要携带租户上下文做权限检查，我们需要在 Runtime 层注入安全拦截
> 4. **轻量级**：LangChain 依赖链重，自研 Runtime 核心代码仅 ~2000 行，测试覆盖率高，易于维护
>
> 但我们借鉴了 LangChain 的优秀思想：ReAct 循环、Chain of Thought 规划。

### Q3: 为什么不用简单的 RAG（Embedding 检索），而是设计 Hybrid RAG？

> **企业知识检索的痛点**：
>
> 纯 Embedding 检索的问题：
> - **专有名词**：Kubernetes、Pod OOM、HPA — Embedding 模型对这些技术术语的语义理解有限
> - **精确匹配**：SOP 编号、错误码、命令参数 — 需要精确的 KV 匹配而非语义匹配
> - **冷启动**：新知识库没有 Embedding，需要 BM25 做回退
>
> **Hybrid RAG 三层架构**：
>
> ```text
> Query → BM25 (关键词) ─┐
>       → Embedding (语义) ─┼→ RRF Fusion → Rerank → Answer
>       → 知识图谱 (实体)  ─┘
> ```
>
> 1. BM25 确保精确匹配（技术术语、编号）
> 2. Embedding 确保语义理解（同义改写、概念匹配）
> 3. RRF 融合算法均衡两种结果
> 4. Rerank 做最终精排
>
> 实测效果：混合检索的 Recall@10 比纯 Embedding 提升约 15~20%。

### Q4: 如何保证企业安全？

> **多层防御体系**：
>
> | 层 | 机制 |
> |---|------|
> | 网络层 | JWT + Refresh Token，API Key 认证 |
> | 应用层 | RBAC（admin/editor/viewer + 细粒度资源权限） |
> | 数据层 | tenant_id 隔离：所有 SQL 查询自动带租户过滤 |
> | 审计层 | 50+ 事件类型，记录谁、何时、做了什么、结果如何 |
> | 限流层 | 每租户速率限制 + Token 配额 |
>
> 关键设计：**在 ORM Repository 层注入 tenant_id 过滤**，确保即使 API 层漏检，数据层也不会跨租户泄露。

### Q5: 多租户如何实现数据隔离？

> **双层隔离策略**：
>
> 1. **请求级隔离**：JWT Token 中携带 `tenant_id`，中间件自动提取注入请求上下文
> 2. **数据级隔离**：所有数据库表都有 `tenant_id` 列，Repository 层基类在查询时自动追加 `.where(tenant_id=...)`
> 3. **Project 级隔离**：在租户内再按 Project 划分，Resource 级别的权限控制
>
> 代码示例（Repository 层）：
>
> ```python
> class BaseRepository:
>     async def _list(self, ...):
>         query = select(self.model).where(self.model.tenant_id == self._get_current_tenant())
>         # ... 自动隔离，上层无需关心租户逻辑
> ```

### Q6: 为什么用 ChromaDB 而不是 Pinecone / Weaviate？

> **私有化部署要求**：
>
> 企业客户要求数据不出私网，不能使用 Pinecone 等 SaaS 向量数据库。ChromaDB 的优势：
> 1. 开源、可本地部署（Docker 一键启动）
> 2. 支持多种 Embedding 模型切换
> 3. 轻量级，资源占用低
> 4. 通过 HTTP API 集成，与后端架构解耦
>
> 如果未来需要更高性能，可以通过统一的 VectorStore 抽象层切换到 Milvus 或 Qdrant。

### Q7: MCP 协议在这项目中的作用？

> **MCP = Managed Cloud Provider 协议适配**
>
> 传统 Agent 只能使用预设的工具。MCP 让 Agent **动态发现和使用外部工具**：
>
> 1. 外部服务（如 K8s API、数据库、GitLab）通过 MCP Server 暴露工具
> 2. Agent 运行时通过 MCP Client 自动发现可用工具
> 3. MCP Tool Adapter 将远程工具包装成本地 BaseTool 接口
> 4. Planner 可以像调用本地工具一样调用远程工具
>
> 举例：Agent 在处理「Pod OOM」故障时，可以自动调用 K8s MCP Server 的 `k8s_get_pods` 和 `k8s_restart_deployment` 工具。

---

## 三、简历关键词

| 类别 | 关键词 |
|------|--------|
| **语言** | Python, TypeScript, JavaScript |
| **框架** | FastAPI, React, SQLAlchemy 2.0, Pydantic |
| **AI/ML** | LLM, RAG, Embedding, Knowledge Graph, Agent, LangChain思想 |
| **数据库** | PostgreSQL, Redis, ChromaDB, SQLite |
| **运维** | Docker, Kubernetes, Helm, Prometheus, Grafana |
| **可观测性** | OpenTelemetry, Structured Logging, Distributed Tracing |
| **安全** | JWT, RBAC, OAuth2, Multi-Tenancy, Audit Logging |
| **工具** | Git, GitHub Actions, Ruff, MyPy, Pytest, Alembic |
| **协议** | REST API, MCP, SSE, Webhook |

---

## 四、项目亮点总结

1. **1000+ 测试用例** — 全模块覆盖，CI 流水线自动化验证
2. **Hybrid RAG 引擎** — BM25 + Embedding + Rerank 三层递进检索
3. **Agent Runtime** — 自研 Planner + Tool + Memory 架构
4. **Workflow 编排** — DAG 自动化，含人工审批节点
5. **企业级安全** — JWT + RBAC + 多租户 + 审计日志
6. **私有化部署** — Docker Compose + Kubernetes + Helm
7. **MCP 协议支持** — Agent 动态发现外部工具
8. **前端 Dashboard** — React + shadcn/ui，5 个核心管理页面