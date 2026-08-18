#!/usr/bin/env bash
# Tear down volumes and re-run demo_start.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
docker compose down -v
exec "$ROOT/scripts/demo_start.sh"
