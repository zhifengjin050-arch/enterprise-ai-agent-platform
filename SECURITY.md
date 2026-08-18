# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |
| < 1.0   | No        |

## Reporting a vulnerability

**Do not open a public GitHub Issue for security reports.**

Please email the maintainers (or use GitHub Security Advisories on this repository) with:

- A description of the issue and impact
- Steps to reproduce, or a proof of concept
- Affected version / commit SHA
- Any suggested fix (optional)

You should receive an acknowledgement within 7 days. We will coordinate a fix and a disclosure timeline before any public advisory.

## Never include in issues or PRs

- Production JWT secrets
- LLM / third-party API keys
- Database passwords
- Real tenant data or customer documents

Use placeholders such as `sk-xxxx` or `change-me-in-production`.

## Production hardening

Before exposing this project on a public network:

1. Set a strong `JWT_SECRET` (16+ random characters). The default is for local development only.
2. Restrict `CORS_ORIGINS` to your frontend origin. Do not use `*`.
3. Replace Docker / Helm secret placeholders (Postgres, Grafana, LLM keys).
4. Run the backend as a non-root user (the production Dockerfile already does this).
5. Keep API keys hashed (the platform stores API keys as SHA-256, never plaintext).
