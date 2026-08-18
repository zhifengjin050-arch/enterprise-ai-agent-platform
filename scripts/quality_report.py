#!/usr/bin/env python3
"""Generate quality baseline report."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent


def _run(cmd: list[str]) -> dict:
    result = subprocess.run(cmd, capture_output=True, cwd=REPO)
    return {
        "stdout": result.stdout.decode("utf-8", errors="replace"),
        "stderr": result.stderr.decode("utf-8", errors="replace"),
        "rc": result.returncode,
    }


def main() -> None:
    print("=" * 60)
    print("Quality Baseline Report")
    print("=" * 60)

    # ruff check
    print("\n--- ruff check ---")
    r = _run(["ruff", "check", "app/", "--statistics"])
    print(r["stdout"][:500])

    # ruff format
    print("\n--- ruff format --check ---")
    rf = _run(["ruff", "format", "app/", "--check"])
    unformatted = [l for l in rf["stdout"].split("\n") if "would be reformatted" in l.lower()]
    print(f"  Would reformat: {len(unformatted)} files")

    # mypy
    print("\n--- mypy ---")
    m = _run(["mypy", "app/", "--ignore-missing-imports"])
    errs = [l for l in m["stdout"].split("\n") if l.strip() and "error:" in l.lower()]
    files = {l.split(":")[0].strip() for l in errs if ":" in l[:20]}
    print(f"  Errors: {len(errs)} in {len(files)} file(s)")
    for e in errs[:5]:
        print(f"    {e}")

    # bandit
    print("\n--- bandit ---")
    b = _run(["bandit", "-r", "app/", "-f", "json"])
    try:
        data = json.loads(b["stdout"])
        results = data.get("results", [])
        metrics = data.get("metrics", {}).get("_totals", {})
        print(f"  Findings: {len(results)}")
        print(f"  High: {metrics.get('CONFIDENCE.HIGH', 0)}, Medium: {metrics.get('CONFIDENCE.MEDIUM', 0)}, Low: {metrics.get('CONFIDENCE.LOW', 0)}")
        for x in results[:10]:
            print(f"    {x['test_id']}: {Path(x['filename']).name}:{x['line_number']} {x['issue_text'][:80]}")
    except json.JSONDecodeError:
        print(f"  Parse failed, stderr: {b['stderr'][:200]}")

    print("\n" + "=" * 60)
    print("DONE — Informational baseline only. No fixes required per Phase A-3.")
    print("=" * 60)


if __name__ == "__main__":
    main()