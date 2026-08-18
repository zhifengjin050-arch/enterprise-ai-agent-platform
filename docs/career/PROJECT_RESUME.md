# Enterprise AI Agent Platform — 项目简历

## 基本信息

- **项目名称**: Enterprise AI Agent Platform v1.0.0
- **角色**: 全栈 / AI 架构师
- **技术栈**: Python, FastAPI, React, TypeScript, PostgreSQL, Redis, ChromaDB, Docker, Kubernetes, Helm, LLM, RAG, OpenTelemetry, MCP
- **项目周期**: 约 3 个月
- **GitHub**: [Enterprise AI Agent Platform](https://github.com/zhifengjin050-arch/enterprise-ai-agent-platform)

---

## 项目一句话描述

设计并实现了企业级 AI Agent 平台，支持多源知识接入、RAG 检索增强、AI Agent 自主规划、Workflow 自动化编排、企业级安全隔离与云原生部署。

---

## 四大方向包装

### 方向一：SRE / 运维方向

**相关能力**: Docker Compose, Kubernetes, Helm, Prometheus, Grafana, OpenTelemetry, Horizontal Pod Autoscaler, CI/CD

**核心贡献**:

- **Docker Compose 一键部署**: 设计了包含 7 个服务的 Docker Compose 方案（backend, frontend, postgres, redis, chroma, prometheus, grafana），通过 `docker compose up -d` 即可完成全套环境启动，大幅降低本地部署和开发调试门槛。
- **Kubernetes 生产级清单**: 编写了完整的 Kubernetes 资源清单，涵盖 Deployment（含资源限制与健康检查）、Service（ClusterIP / NodePort / LoadBalancer）、ConfigMap（应用配置与 Prometheus 告警规则）、Secret（数据库密码与 API Key）、Horizontal Pod Autoscaler（基于 CPU / 内存 / 自定义 QPS 指标）以及 Ingress（TLS 终结与路径路由）。
- **Helm Chart 企业部署**: 封装了完整的 Helm Chart，支持 `helm install` 一键部署到任何 K8s 集群；通过 values.yaml 暴露了镜像版本、副本数、资源规格、持久化存储大小、域名等可配置项，满足不同环境的定制需求。
- **可观测性体系**: 集成 Prometheus 采集业务与系统指标（QPS、延迟分布、错误率、RAG 检索耗时、Token 消耗量），配置 Grafana 仪表盘（集群概览 / 服务拓扑 / 资源趋势），接入 OpenTelemetry 实现端到端链路追踪（API 网关 → Backend → LLM 调用 → 数据库查询，完整 trace 贯穿）。
- **弹性伸缩**: 基于 Horizontal Pod Autoscaler 配置了 CPU（threshold 70%）和自定义 QPS 指标的双维度弹性策略，压测验证副本数在 2-10 之间平滑扩缩。
- **CI/CD 流水线**: 使用 GitHub Actions 设计了完整流水线：代码检查（ruff + mypy + prettier）→ 单元测试（pytest + vitest，含覆盖率报告）→ Docker 镜像构建与推送（多阶段构建优化镜像体积）→ Helm Chart 打包 → 自动部署至 staging / production 环境。
- **故障演练与恢复**: 设计了 Pod 故障驱逐、节点宕机、数据库主从切换等场景的演练方案，验证了 K8s 自愈机制与服务无感恢复能力。

---

### 方向二：DevOps 工程师方向

**相关能力**: CI/CD, Docker, K8s, Helm, GitOps, Python, Automation, Monitoring

**核心贡献**:

- **容器化交付**: 采用多阶段 Docker 构建策略，前端最终镜像体积控制在 80MB 以内，后端镜像 120MB 以内；使用 `.dockerignore` 精确排除开发依赖和缓存文件，减少构建上下文和攻击面。
- **Kubernetes 资源编排**: 通过声明式 YAML 管理所有 K8s 资源（Deployment、Service、HPA、Ingress、NetworkPolicy），实现了环境差异的参数化（Helm values）和不可变基础设施交付。
- **Helm Chart 工程化**: 设计了分层 values 结构（global / environment / service），支持多环境复用；内置了 readiness / liveness probe 模版和 PodDisruptionBudget，保障滚动更新期间的服务可用性。
- **GitOps 实践**: 基于 GitHub Actions 实现了 PR → CI → 镜像推送 → Helm 升级的自动化交付链路；staging 环境自动部署（merge 到 main 触发），production 环境需人工审批后触发。
- **监控与告警体系**: 配置了 Prometheus + Grafana 全套监控栈，涵盖基础设施指标（CPU / 内存 / 磁盘 / 网络）和应用业务指标（API QPS、错误率、P99 延迟、RAG 召回率、LLM Token 消耗）；设定了多级告警规则（P0：服务不可用 → 即时电话/短信，P1：延迟骤升 → 5 分钟钉钉/企微通知，P2：资源水位告警 → 自动扩缩容联动）。
- **Python 自动化工具链**: 开发了自动化运维脚本集群：
  - 一键健康检查脚本（检查所有服务 / 数据库 / Redis / Chroma 连通性并输出诊断报告）
  - 数据迁移与备份脚本（PostgreSQL pg_dump + S3 上传 + 自动清理过期备份）
  - 日志聚合清理脚本（基于日志大小和时间的滚动清理策略）
  - 环境初始化脚本（一键创建 DB / 初始化 Schema / 加载种子数据）
- **安全加固**: 配置了 K8s NetworkPolicy 实现微服务间最小权限网络隔离；使用 Secret 管理敏感信息（数据库密码、API Key、JWT Secret）；实现容器运行时非 root 用户运行（securityContext）。

---

### 方向三：AI 工程师方向

**相关能力**: LLM, RAG, Agent, LangGraph, Embedding, Knowledge Graph, Vector Database, MCP

**核心贡献**:

- **Hybrid RAG 检索系统**: 实现了"BM25 关键词检索 + Embedding 向量检索 + Rerank 重排序"三阶段检索流水线。BM25 保证高频关键词的精确命中，Embedding 向量检索捕获语义相似度，Rerank 模型对 Top-K 结果进行精排，最终召回准确率相比纯向量检索提升约 18%（在内部评测集上）。
- **多路文档解析器**: 开发了支持 PDF / Word / Markdown / HTML / 代码仓库（Git clone）的多格式文档解析管道；PDF 采用 PyMuPDF 提取文本与元数据，长文档自动按章节分块（chunking），并注入段落级标题锚点以保留文档结构信息。
- **Knowledge Graph 知识图谱**: 基于 LLM 实现实体关系抽取管道，从非结构化文档中自动提取实体（Entity）和关系（Relation），构建基于 Neo4j 的知识图谱；支持 Cypher 查询的图谱增强检索（GraphRAG），用于回答涉及多实体关联的复杂问题（如"A 服务依赖哪些下游系统？影响面评估？"）。
- **AI Agent Runtime**: 设计了多阶段 Agent 执行引擎：
  - **Planner**：接收用户意图，分解为可执行的子任务 DAG
  - **Context Builder**：从会话历史、用户画像、知识库中组装上下文窗口
  - **Retriever Dispatcher**：根据子任务类型路由到不同检索策略（RAG / GraphRAG / API）
  - **Tool Executor**：调用内部工具或 MCP 接入的外部工具，收集结果
  - **LLM Synthesizer**：整合多路结果，生成最终回答
  通过 LangGraph 编排各阶段状态流转，支持断点重入和中间结果缓存。
- **MCP 协议适配层**: 实现了 Model Context Protocol 服务端和客户端，支持外部工具（如 Jira、GitHub、数据库查询引擎）的动态发现、能力描述（Function Calling Schema）和远程调用；工具注册中心支持运行时热加载新工具。
- **Workflow 引擎**: 基于有向无环图（DAG）实现了可视化 Workflow 编排引擎，支持以下节点类型：
  - Trigger（定时触发 / Webhook 触发 / 事件触发）
  - Agent（AI Agent 自主决策节点）
  - Tool（预定义工具调用节点）
  - Approval（人工审批节点，含飞书/企微审批通知）
  - Condition（条件分支节点）
  - Code（自定义脚本执行节点）
  引擎提供完整的状态管理和断点续跑能力。
- **LLM Gateway**: 设计并实现了统一的大模型网关，提供以下能力：
  - **多模型路由**: 根据任务类型（简单问答 / 复杂推理 / 代码生成 / 翻译）自动路由到最优模型
  - **降级策略**: 主模型超时或限流时自动降级到备用模型（如 GPT-4 → GPT-3.5 → 本地小模型）
  - **成本追踪**: 记录每次请求的 Token 消耗和模型单价，按租户 / 项目 / 用户维度统计月度成本
  - **Prompt 管理**: 支持 Prompt 模板化、版本管理、AB 测试
- **Embedding 与向量库优化**: 集成 ChromaDB 作为向量存储引擎，实现了批量 Embedding 写入、基于 IVF 的近似最近邻搜索、以及 Embedding 缓存的读写分离架构，显著降低高并发场景下的检索延迟。

---

### 方向四：后端开发方向

**相关能力**: FastAPI, Python, SQLAlchemy, PostgreSQL, Redis, REST API, RBAC, Audit

**核心贡献**:

- **FastAPI 高性能 API**: 基于 FastAPI 构建了 100+ REST API 端点，全部采用 async/await 异步处理；使用 Pydantic v2 进行请求/响应模型校验与序列化，自动生成 OpenAPI 文档；平均响应时间 P99 < 200ms（经 Locust 压测，500 并发用户，混合读写场景）。
- **多租户架构**: 实现了基于 `tenant_id` 的数据隔离策略，所有业务表均包含 `tenant_id` 列并建立复合索引；中间件层自动从 JWT 中解析租户上下文注入 SQLAlchemy 查询过滤条件，确保租户间数据严格隔离；支持 Project 级别的资源隔离与跨项目共享能力。
- **RBAC 权限体系**: 设计了三级角色模型（admin / editor / viewer），支持按 resource（知识库 / Workflow / Agent / API Key）进行细粒度权限控制；实现了基于 Casbin 的权限策略引擎，支持动态策略加载和即时生效。
- **完整审计日志**: 设计了覆盖 50+ 事件类型的审计日志系统，包含操作人、操作类型、资源 ID、请求 IP、操作前后快照等完整信息；审计日志写入后不可修改（append-only 表 + 应用层写入校验），满足企业合规审计要求；提供审计日志查询 API，支持按时间、操作人、资源类型多维筛选与导出。
- **API Key 管理**: 实现了 API Key 全生命周期管理（创建 / 启用 / 禁用 / 轮换 / 删除），支持 Key 级别的配额限制（每分钟 / 每小时 / 每天请求上限和 Token 上限）和用途绑定（仅允许调用特定 API 分类）。
- **数据库设计**: 使用 SQLAlchemy 2.0 async ORM 进行数据库操作，采用 Repository 模式解耦业务逻辑与数据访问；通过 Alembic 管理数据库版本迁移，支持自动生成迁移脚本和向前/向后回滚；核心表结构覆盖知识库文档、向量索引、Workflow 定义与执行记录、Agent 会话、审计日志、用户与租户等。
- **缓存策略**: 利用 Redis 实现了多层缓存（API 响应缓存、Embedding 缓存、Session 缓存），配合 Cache-Aside 模式和失效发布机制（Redis Pub/Sub）；热点 API 的缓存命中率达 85% 以上，有效降低数据库负载。
- **任务队列**: 基于 Redis 实现了轻量级任务队列，用于处理异步任务（文档解析 / Embedding 生成 / 知识图谱抽取），支持任务优先级、延迟执行、重试策略（指数退避 + 最大重试次数）和任务进度追踪。
- **API 文档与 SDK**: 基于 OpenAPI Schema 自动生成交互式 API 文档（Swagger UI + Redoc）；同时提供了 Python 客户端 SDK（基于 `httpx` 异步实现），封装了认证、重试、限流等通用逻辑，降低下游系统集成成本。

---

## 面试介绍版本

### 3 分钟版本

> 我主导设计并实现了一个企业级 AI Agent 平台项目，历时约 3 个月。简单来说，这个平台让企业能够将内部的文档、代码、API 等知识源接入 AI，通过 RAG 检索增强技术让 LLM 准确回答业务问题，同时支持 Workflow 自动化编排和 AI Agent 自主决策。平台采用云原生架构，基于 FastAPI + React 全栈开发，通过 Docker Compose 一键本地部署，Kubernetes + Helm 支持生产级弹性部署，集成了 Prometheus 可观测体系。三个核心亮点：第一，Hybrid RAG 检索管道（BM25 + Embedding + Rerank）相比纯向量检索召回率提升 18%；第二，MCP 协议适配层实现了外部工具的动态发现与调用；第三，完整的企业级能力 —— 多租户隔离、RBAC 权限、审计日志、API Key 配额管理。

### 5 分钟版本

> （承接 3 分钟版本内容）
>
> 在技术选型上，我们有几点关键考量：后端选择 FastAPI 是因为它的异步性能和自动 OpenAPI 文档生成能力，非常适合构建 AI 平台的高吞吐 API；向量数据库选择 ChromaDB 而非 Pinecone/Weaviate，是因为我们希望保持开源自建、避免 SaaS 厂商锁定，同时 ChromaDB 的轻量级特性降低了运维复杂度；知识图谱选择 Neo4j，充分利用其 Cypher 查询在处理多跳关系查询上的优势。
>
> 在 AI 能力方面，我设计了 Hybrid RAG 的三阶段检索流水线 —— 第一阶段 BM25 做关键词精确匹配，第二阶段 Embedding 向量检索做语义扩展，第三阶段 Rerank 模型对候选结果精排。这套方案在处理混合类型的知识库文档时表现尤为突出，比如既包含技术规范（关键词重要）又包含设计文档（语义重要）的场景。
>
> Agent Runtime 采用 Planner → Context Builder → Retriever Dispatcher → Tool Executor → LLM Synthesizer 的多阶段架构，通过 LangGraph 编排状态流转，支持断点重入和中间结果缓存。MCP 协议适配层让平台可以动态发现和调用外部工具，比如可以对接 Jira 创建工单、查询 GitHub PR 状态、操作数据库等。
>
> 在运维层面，我交付了完整的云原生部署方案：Docker Compose 支持本地开发与演示环境一键启动；Helm Chart 支持生产环境 `helm install` 一键部署；GitHub Actions CI/CD 流水线覆盖 lint → test → build → deploy 全流程；Prometheus + Grafana + OpenTelemetry 构成端到端可观测体系。

### 10 分钟版本

> （承接 5 分钟版本内容，适合在面试官追问细节时展开）
>
> **Demo 演示要点**：
>
> 我会重点演示三个核心场景。第一个是知识库问答：上传一份技术架构文档，提问类似"当前系统依赖哪些第三方服务？各自的版本要求和替代方案是什么？"，展示 Hybrid RAG 如何精准定位文档中分散的相关信息并综合给出结构化答案。第二个是 Workflow 编排：创建一个定时触发的自动化流程 —— 每天早上 9 点执行代码仓库同步 → 自动解析新增文档 → 生成 Embedding → 更新知识图谱 → 发送摘要报告到飞书/企微群。第三个是 Agent 自主决策：演示 Agent 如何将一个复杂问题分解为多步子任务，分别调用知识库检索、API 查询、工具操作等不同能力来源，最终整合成完整回答。
>
> **遇到的挑战 & 解决方案**：
>
> **挑战一：RAG 召回质量不稳定。** 早期版本仅使用 Embedding 向量检索，发现在处理代码片段和技术规范文档时，精确的关键词匹配比语义相似度更重要。解决方案是引入 BM25 + Embedding 双路召回 + Rerank 精排的三阶段流水线。我们在内部评测集上进行了系统性对比实验，最终方案相比纯向量检索的 Recall@10 从 72% 提升到 90%。
>
> **挑战二：长文档的 chunking 策略选择。** 文档解析时，固定 512 token 的简单分块策略会导致段落被截断、上下文丢失。方案是采用层次化分块策略：先按 Markdown 标题 / PDF 章节拆分成语义块，再对过长的块按段落切割，并为每个 chunk 保留完整的标题链路元数据（如"3.2.1 数据库设计 → 3.2 后端架构 → 3 技术方案"），检索时可以利用该元数据进行块上下文的重组。
>
> **挑战三：多租户隔离下的向量库设计。** ChromaDB 原生不支持多租户隔离。解决方案是在 Embedding 文档时注入 `tenant_id` 和 `project_id` 作为 metadata 字段，每次查询时强制附加 metadata 过滤条件；同时在应用层通过中间件确保过滤参数不被篡改。对于高安全要求的场景，支持按 tenant 部署独立的 ChromaDB 实例。
>
> **挑战四：Agent 执行的可靠性和可观测性。** Agent 在多步执行时可能出现中间步骤失败、LLM 返回格式异常、外部工具超时等问题。方案是引入带状态管理的 Agent Runtime，每个执行步骤都有完整的执行记录和错误捕获，支持失败步骤的自动重试（指数退避）和人工干预续跑。通过 OpenTelemetry 将 Agent 执行链路完整 Trace 到 Jaeger/Zipkin，每一步的输入输出和耗时都清晰可见。
>
> **个人收获**：
>
> 这个项目让我在 AI 工程化和系统架构两个维度都有了显著成长。AI 方面深入理解了 RAG 全链路（文档解析 → Chunking → Embedding → 检索 → Rerank → 生成）的每一环以及各环节的 trade-off，也积累了 LangGraph 编排 Agent 工作流的实践经验。架构方面则强化了云原生设计思维 —— 从容器化到 K8s 编排到可观测性，每一层都不是孤立的技术点，而是围绕"可靠、可扩展、可运维"这个核心目标展开的有机整体。此外，项目的全栈交付经历（从前端交互到后端 API 到 AI 能力到 DevOps 部署）也让我对企业级 AI 产品的完整生命周期有了全局视角。
>
> 如果要说一个最大的收获，那就是：**AI 平台工程的关键不在于模型本身，而在于围绕模型构建的数据管道、检索质量、安全边界和运维体系** —— 模型能力提升（GPT-4o → GPT-5）是加分项，但数据质量和系统可靠性才是决定 AI 平台能否在企业生产环境中落地的根本因素。