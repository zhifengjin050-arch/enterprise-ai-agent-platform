#!/usr/bin/env python3
"""Convenience alias: initialize demo data.

Usage:
    python scripts/demo_init.py

Equivalent to: python scripts/init_demo_data.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def main() -> None:
    script = ROOT / "scripts" / "init_demo_data.py"
    if not script.exists():
        print(f"Error: {script} not found.", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()