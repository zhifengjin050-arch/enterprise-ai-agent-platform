#!/usr/bin/env python3
"""Verify demo pack files exist. Does not start Docker or read .env secrets."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "demo/README.md",
    "demo/seed.yaml",
    "demo/documents/k8s_ops.md",
    "demo/documents/incident_sop.md",
    "scripts/demo_start.sh",
    "scripts/demo_start.ps1",
    "scripts/demo_seed.py",
    ".env.example",
    "docker-compose.yml",
]


def main() -> int:
    missing = [rel for rel in REQUIRED if not (ROOT / rel).exists()]
    if missing:
        print("missing:")
        for m in missing:
            print(" -", m)
        return 1
    print("Demo pack OK. Next:")
    print("  cp .env.example .env")
    print("  ./scripts/demo_start.sh   # or .\\scripts\\demo_start.ps1")
    print("  open http://localhost   (admin / admin123)")
    print("Do not commit .env")
    return 0


if __name__ == "__main__":
    sys.exit(main())
