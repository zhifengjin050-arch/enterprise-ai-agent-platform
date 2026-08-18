# Changelog

All notable changes to the **Enterprise AI Agent Platform** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

Release notes and install walkthrough: [docs/RELEASE_GUIDE.md](docs/RELEASE_GUIDE.md).

---

## [1.0.0] — 2026-08-18 — Release Candidate

### Added

#### 🤖 Enterprise AI Agent Runtime
- Planner with ReAct, Plan-and-Execute, and Reflection strategies
- Context Engine with window, summary, and hybrid modes
- Tool System with 30+ built-in tools and unified BaseTool interface
- Memory (short-term, long-term, working memory)
- LLM Gateway with multi-model routing, fallback, and cost tracking

#### 📚 Knowledge Intelligence
- Smart document chunking (Markdown, PDF, DOCX) with overlapping strategies
- Hybrid RAG pipeline: BM25 full-text + Embedding vector + Rerank fusion
- Knowledge Graph: entity extraction, relation building, graph traversal queries
- Multi-vector retrieval with configurable embedding models (text-embedding-3-small, bge-m3)
- Semantic search, full-text search, and hybrid search APIs

#### 🔗 Connector Framework
- Unified connector lifecycle: configure → validate → enable → monitor → disable
- Built-in connectors: Feishu Docs, GitLab, Yuque
- Capability-based plugin discovery
- Incremental sync with cursor + checkpoint + breakpoint resume

#### ⚙️ Workflow Automation Engine
- DAG-based workflow definition with JSON DSL
- 6 node types: Trigger, Agent, Tool, Condition, Approval, End
- 4 trigger types: API, Webhook, Schedule, SyncEvent
- Human approval: confirm, reject, timeout (with notification)
- Full lifecycle: CREATED → RUNNING → WAITING → PAUSED → COMPLETED/FAILED
- Pause, resume, and cancel operations
- Observability integration: traces, metrics, audit for every workflow execution

#### 🔒 Enterprise Security & Multi-Tenancy
- JWT authentication (access + refresh tokens)
- RBAC with admin/editor/viewer roles and fine-grained resource permissions
- Organization + Project multi-tenant data isolation
- API Key management with automatic generation and revocation
- Audit logging: 50+ event types with WORM-compliant storage
- Rate limiting and quota management per tenant

#### 📊 Observability
- OpenTelemetry distributed tracing
- Prometheus metrics: 50+ metrics covering HTTP, Agent, LLM, Workflow
- Grafana dashboard with pre-built panels
- Structured JSON logging with request ID correlation
- LLM cost tracking by model, tenant, and time period
- Error rate monitoring and alerting

#### 🖥️ Frontend Dashboard (React + TypeScript)
- Dashboard homepage with system metrics overview
- Agent management page with runtime trace timeline
- Knowledge management with search and graph visualization
- Workflow definition and execution monitoring
- System monitoring with Prometheus metrics and LLM cost breakdown
- shadcn/ui components with dark mode support

#### 🐳 Deployment
- Docker Compose: 7 services (backend, frontend, postgres, redis, chroma, prometheus, grafana)
- Multi-stage Dockerfile for optimized images
- Nginx reverse proxy with SPA fallback
- Prometheus + Grafana monitoring stack

#### ☸️ Kubernetes & Helm
- Kubernetes manifests: Namespace, Deployment, Service, ConfigMap, Secret, HPA
- Helm Chart with configurable values, templates, and ingress
- Horizontal Pod Autoscaler (CPU 70% / memory 80%, 2-10 replicas)

#### 🔌 MCP (Managed Cloud Provider) Integration
- MCP client for remote tool server communication
- MCP tool adapter: wraps remote tools into BaseTool interface
- MCP adapter registry: server registration and tool discovery
- Automatic discovery on startup via configuration
- REST API endpoints for runtime tool listing

#### 📋 Open Source Engineering
- GitHub Actions CI: lint, test (Python 3.11/3.12), docker build, frontend build
- Ruff linter and formatter configuration
- MyPy type checking baseline
- Pre-commit hooks for code quality
- Comprehensive README with architecture diagram, quick start, roadmap

### Fixed
- LRU cache eviction: replaced `min()`-based eviction with `OrderedDict` FIFO + `move_to_end` for correct LRU semantics
- Cache global state leak: `clear_cache()` now properly resets module-level configuration
- Workflow engine test timeout: added `pytest-timeout` with thread mode (Windows-compatible)
- Version consistency: unified version strings across `app/main.py`, `pyproject.toml`, `Chart.yaml`, `frontend/package.json`
- Frontend TypeScript strict mode errors: optional fields for API response types
- Ruff configuration deduplication: removed standalone `ruff.toml`, unified in `pyproject.toml`
- Bandit security baseline generated and documented

### Known
- Workflow engine tests using `asyncio.get_event_loop().run_in_executor` may timeout in CI due to background task vs test DB session conflict — mitigated with 300s pytest-timeout
- Yuque and Feishu connectors have stub implementations pending OAuth credential configuration

---

## [0.9.0] — 2026-08-10 — Workflow Automation Engine

### Added
- WorkflowEngine with DAG orchestration
- WorkflowDefinition CRUD with JSON DSL parsing
- Node system: TriggerNode, AgentNode, ToolNode, ConditionNode, ApprovalNode, EndNode
- Workflow triggers: API, Webhook, Schedule, SyncEvent
- ApprovalService with confirm/reject/timeout
- Workflow observability integration (traces, metrics, audit events)
- Migration: `0011_workflow` (workflows, workflow_nodes, workflow_executions, workflow_events)
- API: `/api/workflows` (CRUD + execute/pause/resume/cancel)
- 156+ workflow engine tests

---

## [0.8.0] — 2026-08-03 — Observability

### Added
- OpenTelemetry tracing with OTLP exporter
- Prometheus metrics: HTTP, Agent, LLM, Workflow
- Structured JSON logging with `request_id` correlation
- LLM cost tracking and aggregation
- Grafana dashboard definition
- Metrics API endpoints (/api/metrics/*)
- Health check with component dependency validation

---

## [0.7.0] — 2026-07-27 — Enterprise Security

### Added
- JWT authentication with access/refresh tokens
- RBAC with fine-grained resource permissions
- Multi-tenant data isolation (organization/project)
- API Key management
- Audit logging (50+ event types)
- Rate limiting and quota enforcement

---

## [0.6.0] — 2026-07-20 — AI Agent Runtime

### Added
- Planner: ReAct, Plan-and-Execute, Reflection strategies
- Context Engine: window, summary, hybrid mode
- Tool System: 30+ built-in tools
- Memory: short-term, long-term, working memory
- LLM Gateway: multi-model routing, fallback, cost tracker
- Agent execution API with SSE streaming

---

## [0.5.0] — 2026-07-13 — Knowledge Intelligence

### Added
- Smart document chunking
- Hybrid RAG (BM25 + embedding + rerank)
- Knowledge Graph with entity/relation extraction
- Semantic search, full-text search, hybrid search
- Embedding management with multi-model support

---

## [0.4.0] — 2026-07-06 — Sync Engine

### Added
- Incremental sync with cursor-based pagination
- Checkpoint and breakpoint resume
- Failure retry with exponential backoff
- Sync job scheduling and monitoring

---

## [0.3.0] — 2026-06-29 — Connector Framework

### Added
- Unified connector lifecycle
- Feishu Docs connector
- GitLab connector
- Yuque connector
- Capability-based plugin system

---

## [0.2.0] — 2026-06-22 — Foundation

### Added
- FastAPI application scaffold
- SQLAlchemy 2.0 async ORM with Alembic migrations
- PostgreSQL + Redis integration
- ChromaDB vector store
- Unified error handling and response models
- Structured logging

---

## [0.1.0] — 2026-06-15 — Initial Prototype

### Added
- Project skeleton with modular architecture
- Basic document management
- LLM integration placeholders
- Development environment setup