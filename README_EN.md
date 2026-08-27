<div align="center">

<img src="docs/images/hero.png" alt="Enterprise AI Agent Platform" width="100%" />

# Enterprise AI Agent Platform

**Enterprise knowledge-base Agent: document processing, hybrid RAG, vector search, and permission control.**

An enterprise AI Agent platform with knowledge intelligence, workflow automation, multi-tenant security, and cloud-native deployment.

[中文](README.md) · [Release Guide](docs/RELEASE_GUIDE.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

[![CI](https://github.com/zhifengjin050-arch/enterprise-ai-agent-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/zhifengjin050-arch/enterprise-ai-agent-platform/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)]()
[![Release](https://img.shields.io/badge/Release-v1.0.0-blue)]()
[![License](https://img.shields.io/badge/License-Apache%202.0-red)]()
[![Tests](https://img.shields.io/badge/Tests-1060%20passed-brightgreen)]()

</div>

---

## Introduction

This is not a chatbot. It is infrastructure that turns enterprise knowledge into executable automation:

- Ingest documents from Feishu, Yuque, and GitLab
- Answer with hybrid retrieval plus a knowledge graph
- Plan and call tools through the Agent Runtime
- Orchestrate approvals and incident handling with the Workflow Engine
- Isolate tenants with JWT, RBAC, API keys, and audit logs
- Deploy with Docker Compose or Kubernetes / Helm

Built for SRE, DevOps, AI, and platform engineers who need a private knowledge copilot.

See [docs/images/system_architecture.md](docs/images/system_architecture.md) for the full diagrams.

---

## Demo

[![Demo video](docs/videos/cover.png)](docs/videos/demo.mp4)

Click the cover to watch the walkthrough (Chinese narration + subtitles).

---

## Capabilities

| Module | Capability |
|--------|------------|
| Connector Framework | Feishu / Yuque / GitLab connectors with unified config |
| Sync Engine | Full and incremental sync, jobs, retries |
| Knowledge Intelligence | Chunking, tagging, document lifecycle |
| Hybrid RAG | Vector search fused with full-text search |
| Knowledge Graph | Entity / relation extraction and graph query |
| Agent Runtime | Planner, tool registry, memory, LLM gateway |
| Workflow Engine | DAG nodes, approvals, triggers, run lifecycle |
| Multi Tenant Security | JWT, RBAC, tenant isolation, API keys, audit |
| Observability | OpenTelemetry, Prometheus, Grafana, LLM cost |
| MCP Integration | Tool discovery, registry, remote MCP calls |
| Docker | One-command `docker compose up -d` |
| Kubernetes | Deployment / Service / HPA / Ingress |
| Helm | `charts/enterprise-ai-platform` |

### Feature Matrix

Full list: [docs/showcase/FEATURE_MATRIX.md](docs/showcase/FEATURE_MATRIX.md).

| Area | v1.0.0 |
|------|--------|
| Connector Framework | Feishu / Yuque / GitLab, unified config and sync records |
| Sync Engine | Full / incremental jobs, retries, checkpoints |
| Knowledge Intelligence | Markdown / PDF / DOCX chunking and tagging |
| Hybrid RAG | Vector + full-text + optional rerank |
| Knowledge Graph | Entity / relation extraction and graph query |
| Agent Runtime | Planner, tool registry, memory, LLM gateway |
| Workflow Engine | DAG, approval, API / Webhook / Schedule triggers |
| Multi Tenant Security | JWT, RBAC, tenant isolation, API keys, audit |
| Observability | OpenTelemetry, Prometheus, Grafana, LLM cost |
| MCP Integration | Discovery, registry, remote calls |
| Docker / K8s / Helm | Compose + manifests + chart + HPA |

---

## Architecture

<img src="docs/images/architecture_overview.png" alt="Architecture overview" width="100%" />

```mermaid
flowchart TB
    Frontend["Frontend"] --> API["API Gateway"]
    API --> Agent["Agent Runtime"]
    Agent --> Workflow["Workflow Engine"]
    Workflow --> Knowledge["Knowledge Intelligence"]
    Knowledge --> Vector["Vector Search"]
    Knowledge --> Graph["Knowledge Graph"]
    Knowledge --> Docs["Document Store"]
    Knowledge --> Connector["Connector Framework"]
    Connector --> Feishu["Feishu"]
    Connector --> Yuque["Yuque"]
    Connector --> GitLab["GitLab"]
    Security["Security Layer"] -.-> API
    Observability["Observability Layer"] -.-> Agent
    MCP["MCP Layer"] -.-> Agent
```

A Security Layer (JWT / RBAC / tenant / audit), Observability Layer (traces / metrics / alerts), and MCP Layer (discovery / registry / remote tools) cut across the runtime.

---

## RAG Pipeline

<img src="docs/images/rag-pipeline.png" alt="RAG pipeline" width="100%" />

Connectors ingest documents → chunk / embed → vector + full-text + graph → hybrid retrieve → rerank → LLM answer with citations. Access is bounded by tenant isolation and RBAC.

```mermaid
flowchart LR
    Docs[Documents] --> Conn[Connector]
    Conn --> Chunk[Chunking]
    Chunk --> Emb[Embedding]
    Emb --> VS[Vector Search]
    Emb --> FT[Full-text]
    Emb --> KG[Knowledge Graph]
    VS --> Hyb[Hybrid Retriever]
    FT --> Hyb
    KG --> Hyb
    Hyb --> Rank[Rerank]
    Rank --> LLM[LLM + citations]
```

### Evaluation

| Check | Result |
|-------|--------|
| Stable pytest (workflow excluded on Windows) | 998 passed, 3 skipped |
| `python -m compileall app/` | success |
| Frontend production build | success |
| Retrieval | Hybrid vector + BM25; optional graph boost and rerank |

See [docs/RELEASE_GUIDE.md](docs/RELEASE_GUIDE.md). The workflow suite runs in CI with timeout protection.

---

## Data flow

```mermaid
flowchart LR
    Q["User question"] --> P["Agent Planner"]
    P --> T["Tool calling"]
    T --> R["Retriever"]
    R --> G["Knowledge Graph"]
    G --> L["LLM"]
    L --> A["Response"]
```

---

## Deployment

```mermaid
flowchart TB
    subgraph compose [Docker Compose]
        FE["Frontend"] --> BE["Backend"]
        BE --> PG["PostgreSQL"]
        BE --> RD["Redis"]
        BE --> CH["ChromaDB"]
    end
    subgraph k8s [Kubernetes]
        Ing["Ingress"] --> Svc["Service"] --> Pod["Pod"]
        Pod --> PG2["Database"]
        Pod --> RD2["Redis"]
    end
```

```bash
helm install enterprise-ai ./charts/enterprise-ai-platform \
  --namespace enterprise-ai --create-namespace
```

---

## Tech stack

FastAPI · SQLAlchemy 2.0 · React 18 · TypeScript · PostgreSQL · Redis · ChromaDB · Prometheus · Grafana · Docker · Helm

---

## Quick start

```bash
git clone https://github.com/zhifengjin050-arch/enterprise-ai-agent-platform.git
cd enterprise-ai-agent-platform
cp .env.example .env
docker compose up -d
# Linux/macOS
./scripts/demo_start.sh
# Windows
.\scripts\demo_start.ps1
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost |
| OpenAPI | http://localhost:8000/docs |
| Grafana | http://localhost:3000 |

Demo tenant `CloudTech`, user `admin`, agent `Enterprise Assistant`, workflow `Incident Analysis`.

Set `JWT_SECRET` and restrict `CORS_ORIGINS` before any public deploy. See [SECURITY.md](SECURITY.md).

---

## API examples

OpenAPI: http://localhost:8000/docs

```bash
curl http://localhost:8000/api/health

curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

curl -X POST http://localhost:8000/api/knowledge/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Pod OOM","top_n":5}'

curl -X POST http://localhost:8000/api/agents/<agent_id>/execute \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query":"How should we debug frequent Pod OOM in production?"}'
```

| Prefix | Area |
|--------|------|
| `/api/health` | Health |
| `/api/auth` | Login / JWT |
| `/api/knowledge` | Documents and hybrid search |
| `/api/agents` | Agent CRUD and execute |
| `/api/workflows` | Definitions and runs |
| `/api/connectors` | Connector config |
| `/metrics` | Prometheus |

---

## Test results

| Check | Result |
|-------|--------|
| `python -m compileall app/` | success |
| pytest stable suite (workflow excluded on Windows hang) | **998 passed, 3 skipped** |
| `cd frontend && npm run build` | success |
| Docker Compose / Kubernetes / Helm | manifests and chart ready |

CI: `.github/workflows/ci.yml`.

---

## Roadmap

**v1.0.0 (current):** Agent Runtime, Hybrid RAG, Knowledge Graph, Workflow, Connectors, multi-tenant security, observability, MCP, Docker / K8s / Helm.

Later (out of this release):

- Dedicated Connector / Security dashboard pages
- More connectors and eval sets
- Richer workflow visual designer

---

## Screenshots

| Dashboard | Agent | Knowledge |
|-----------|-------|-----------|
| ![Dashboard](docs/images/dashboard.png) | ![Agent](docs/images/agent-chat.png) | ![Search](docs/images/knowledge-search.png) |

| Architecture | RAG Pipeline |
|--------------|--------------|
| ![Architecture](docs/images/architecture_overview.png) | ![RAG](docs/images/rag-pipeline.png) |

Additional runtime pages live in `docs/screenshots/`.

---

## License

Apache-2.0. See [LICENSE](LICENSE).

Contribute via [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

More: [Release Guide](docs/RELEASE_GUIDE.md) · [GitHub publish notes](docs/GITHUB_PUBLISH.md) · [Checklist](docs/GITHUB_RELEASE_CHECKLIST.md)
