#!/usr/bin/env python3
"""Run quality baseline and produce a markdown report."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).parent.parent


def _run(cmd: list[str]) -> dict:
    result = subprocess.run(
        cmd,
        capture_output=True,
        cwd=REPO,
    )
    return {
        "stdout": result.stdout.decode("utf-8", errors="replace"),
        "stderr": result.stderr.decode("utf-8", errors="replace"),
        "rc": result.returncode,
    }


def main() -> None:
    report_lines: list[str] = []
    report_lines.append("# Quality Baseline Report")
    report_lines.append("")
    report_lines.append(f"Generated: {__import__('datetime').datetime.now().isoformat()}")
    report_lines.append("")
    report_lines.append(
        "> **Note**: This is an informational baseline only. No large-scale fixes required per Phase A-3 rules."
    )
    report_lines.append("")

    # --- ruff check ---
    report_lines.append("## ruff check (lint)")
    ruff = _run(["ruff", "check", "app/", "--statistics"])
    # Parse the summary line
    summary_line = (
        [l for l in ruff["stdout"].split("\n") if l.startswith("Found")][0]
        if any(l.startswith("Found") for l in ruff["stdout"].split("\n"))
        else "N/A"
    )
    report_lines.append(f"- **Total errors**: {summary_line}")
    # Parse rule counts
    for line in ruff["stdout"].split("\n"):
        line = line.strip()
        if line and line[0].isdigit() and "\t" in line:
            parts = line.split("\t")
            if len(parts) >= 3:
                count = parts[0].strip()
                rule = parts[1].strip()
                report_lines.append(f"  - {rule}: {count}")
    report_lines.append("")

    # --- ruff format ---
    report_lines.append("## ruff format (style)")
    ruff_fmt = _run(["ruff", "format", "app/", "--check"])
    fmt_lines = [l for l in ruff_fmt["stdout"].split("\n") if "would be reformatted" in l.lower()]
    report_lines.append(f"- **Files to reformat**: {len(fmt_lines)}")
    report_lines.append("")

    # --- mypy ---
    report_lines.append("## mypy (type check)")
    mypy = _run(["mypy", "app/", "--ignore-missing-imports"])
    err_lines = [l for l in mypy["stdout"].split("\n") if l.strip() and "error:" in l.lower()]
    unique_files = set()
    for l in err_lines:
        parts = l.split(":")
        if len(parts) >= 2:
            unique_files.add(parts[0].strip())
    report_lines.append(f"- **Errors**: {len(err_lines)} in {len(unique_files)} file(s)")
    for l in err_lines[:5]:
        report_lines.append(f"  - `{l.strip()}`")
    report_lines.append("")

    # --- bandit ---
    report_lines.append("## bandit (security)")
    bandit = _run(["bandit", "-r", "app/", "-f", "json"])
    try:
        data = json.loads(bandit["stdout"])
        results = data.get("results", [])
        metrics = data.get("metrics", {}).get("_totals", {})
        report_lines.append(f"- **Total findings**: {len(results)}")
        report_lines.append(
            f"- **Confidence**: High={metrics.get('CONFIDENCE.HIGH', 0)}, Medium={metrics.get('CONFIDENCE.MEDIUM', 0)}, Low={metrics.get('CONFIDENCE.LOW', 0)}"
        )
        for x in results[:10]:
            report_lines.append(
                f"  - `{x['test_id']}`: {Path(x['filename']).relative_to(REPO)}:{x['line_number']} — {x['issue_text'][:80]}"
            )
    except json.JSONDecodeError:
        report_lines.append(f"- **Parse failed**: stdout={bandit['stdout'][:100]}")
    report_lines.append("")

    # --- Summary ---
    report_lines.append("## Summary")
    report_lines.append("")
    report_lines.append("| Tool | Result | Action |")
    report_lines.append("|------|--------|--------|")
    report_lines.append(
        f"| ruff lint | {summary_line} | Fix with `ruff check app/ --fix` (opt-in) |"
    )
    report_lines.append(
        f"| ruff format | {len(fmt_lines)} files need formatting | Fix with `ruff format app/` (opt-in) |"
    )
    report_lines.append(
        f"| mypy | {len(err_lines)} errors in {len(unique_files)} files | Fix selectively (opt-in) |"
    )
    report_lines.append(
        f"| bandit | {len(results) if 'results' in dir() else '?'} findings | Review high-severity items (opt-in) |"
    )
    report_lines.append("")
    report_lines.append("---")
    report_lines.append(
        "All baselines are informational. No code modifications required for Phase A-3."
    )

    # Write report
    output_path = REPO / "docs" / "QUALITY_BASELINE_REPORT.md"
    output_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Report written to {output_path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
