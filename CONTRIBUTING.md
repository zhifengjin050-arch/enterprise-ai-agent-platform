# Contributing to Enterprise AI Agent Platform

Thank you for considering a contribution. This document describes how to set up a local environment, the coding standards we follow, and how to submit a pull request.

## Development setup

```bash
git clone https://github.com/<owner>/enterprise-ai-agent-platform.git
cd enterprise-ai-agent-platform
cp .env.example .env

python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt

cd frontend && npm ci && cd ..
```

Run the stack:

```bash
docker compose up -d
# or local backend
uvicorn app.main:app --reload --port 8000
```

Load demo data:

```bash
python scripts/demo_seed.py
```

## Tests

```bash
python -m compileall app/
python -m pytest tests/ --ignore=tests/workflow --ignore=tests/test_workflow
cd frontend && npm run build
```

Workflow engine tests are excluded from the default local suite (known hang on Windows). CI still runs lint + the remaining tests.

## Code style

| Area | Tool |
|------|------|
| Python lint / format | `ruff check` / `ruff format` |
| Type hints | mypy (baseline; not a merge blocker) |
| Frontend | TypeScript strict + Vite build |
| Commits | [Conventional Commits](https://www.conventionalcommits.org/) |

Examples:

```
feat: add helm ingress TLS option
fix: reset LLM cache config between tests
docs: add English README
```

## Pull request process

1. Fork and create a branch: `git checkout -b feat/short-description`
2. Keep the change focused. Do not mix refactors with feature work.
3. Add or update tests when you change behavior.
4. Run ruff, pytest (non-workflow), and frontend build locally.
5. Fill in the PR template and link related issues.

## What we will not merge

- Secrets, `.env` files, API keys, or production credentials
- Unrelated large refactors
- `print()` debugging left in `app/`
- Changes that break the existing non-workflow test suite without discussion

## Questions

Open a GitHub Discussion or Issue. Do not report security issues in public Issues — see [SECURITY.md](SECURITY.md).
