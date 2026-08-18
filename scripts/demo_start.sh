#!/usr/bin/env bash
# Check Docker, start compose, wait for health, seed demo data.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required"
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose is required"
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

echo "Starting services..."
docker compose up -d

echo "Waiting for backend health..."
for i in $(seq 1 60); do
  if curl -fsS http://localhost:8000/api/health >/dev/null 2>&1; then
    echo "Backend is healthy"
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "Timeout waiting for /api/health"
    exit 1
  fi
  sleep 2
done

python scripts/demo_seed.py
echo "Demo ready: http://localhost  (admin / admin123)"
