# v1.0.0 Release Guide

Enterprise AI Agent Platform — first public release.

## Positioning

A private, production-oriented AI Agent platform: knowledge intelligence, workflow automation, multi-tenant security, and cloud-native deploy. Not a chatbot wrapper.

## Core features

- Agent Runtime: planner, tools, memory, LLM gateway
- Knowledge Intelligence: chunking, hybrid RAG, knowledge graph
- Workflow Engine: DAG, approval, triggers
- Connector + Sync: Feishu / Yuque / GitLab
- Security: JWT, RBAC, tenant isolation, API keys, audit
- Observability: OpenTelemetry, Prometheus, Grafana
- MCP tool adapter
- Docker Compose + Kubernetes + Helm

## Install

```bash
git clone https://github.com/zhifengjin050-arch/enterprise-ai-agent-platform.git
cd enterprise-ai-agent-platform
cp .env.example .env
```

Python 3.11+ for local backend; Node 22 for the dashboard.

## Docker

```bash
docker compose up -d
./scripts/demo_start.sh          # Linux / macOS
.\scripts\demo_start.ps1         # Windows
```

Services: backend `:8000`, frontend `:80`, postgres `:5432`, redis `:6379`, chroma `:8001`, prometheus `:9090`, grafana `:3000`.

## Kubernetes

```bash
kubectl apply -f deploy/kubernetes/
# or
helm install enterprise-ai ./charts/enterprise-ai-platform \
  --namespace enterprise-ai --create-namespace
```

Replace secrets in `deploy/kubernetes/secret.yaml` or Helm `values.yaml` before production.

## Demo flow

1. Start the stack.
2. Seed tenant **CloudTech**, user **admin**, documents, agent **Enterprise Assistant**, workflow **Incident Analysis**.
3. Open http://localhost
4. Search knowledge, inspect workflows, open Monitor.

Reset:

```bash
./scripts/demo_reset.sh
```

Demo files live in [`demo/`](../demo/).

## API

OpenAPI: http://localhost:8000/docs

| Prefix | Area |
|--------|------|
| `/api/health` | Health |
| `/api/knowledge` | Documents and search |
| `/api/agents` | Agent CRUD and execute |
| `/api/workflows` | Workflow definitions and runs |
| `/api/auth` | Login / JWT |
| `/api/connectors` | Connector config |
| `/metrics` | Prometheus |

## Test results (v1.0.0)

Verified on 2026-08-18 (Windows / Python 3.12):

| Check | Result |
|-------|--------|
| pytest (excluding hanging workflow suite) | **998 passed, 3 skipped** |
| workflow collection (`tests/workflow` + `tests/test_workflow`) | 218 collected, not executed locally |
| `python -m compileall app/` | success |
| `cd frontend && npm run build` | success |

Workflow engine tests are excluded locally because of a known hang on Windows; `pytest-timeout` protects CI. The README test badge keeps the historical full-suite figure.

## More

- [CHANGELOG.md](../CHANGELOG.md)
- [SECURITY.md](../SECURITY.md)
- [docs/INTERVIEW_GUIDE.md](INTERVIEW_GUIDE.md)
