#!/usr/bin/env python3
"""Generate quality baseline report (avoids PowerShell encoding issues by writing to file)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, cwd=REPO)
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return result.stdout.decode("gbk", errors="replace")


def main() -> None:
    lines: list[str] = []
    lines.append("# Quality Baseline Report — Enterprise AI Agent Platform v1.0 RC")
    lines.append("")
    lines.append(f"*Generated: {__import__('datetime').datetime.now().isoformat()}*")
    lines.append("")
    lines.append("> **Note**: Informational baseline only. No mass fixes required per Phase A-3 rules.")
    lines.append("")

    # --- ruff check ---
    lines.append("## ruff (lint)")
    ruff_out = _run(["ruff", "check", "app/", "--statistics"])
    lines.append("```")
    lines.append(ruff_out.rstrip())
    lines.append("```")
    lines.append("")
    n_errors = len([l for l in ruff_out.split("\n") if l.strip() and l[0].isdigit()])
    lines.append(f"- **Total error categories**: {n_errors}")
    # count total errors
    total_errs = 0
    for l in ruff_out.split("\n"):
        ls = l.strip()
        if ls and ls[0].isdigit():
            try:
                total_errs += int(ls.split("\t")[0].strip())
            except (ValueError, IndexError):
                pass
    lines.append(f"- **Total occurrences**: ~{total_errs}")
    lines.append("")

    # --- ruff format ---
    lines.append("## ruff (format)")
    fmt_out = _run(["ruff", "format", "app/", "--check"])
    n_unfmt = len([l for l in fmt_out.split("\n") if "would be reformatted" in l.lower()])
    lines.append(f"- **Files to reformat**: {n_unfmt}")
    lines.append("")

    # --- mypy ---
    lines.append("## mypy (type check)")
    mypy_out = _run(["mypy", "app/", "--ignore-missing-imports", "--no-error-summary"])
    err_lines = [l for l in mypy_out.split("\n") if l.strip() and "error:" in l.lower()]
    unique_files = set()
    for l in err_lines:
        parts = l.split(":")
        if len(parts) >= 2:
            unique_files.add(parts[0].strip())
    lines.append(f"- **Errors**: {len(err_lines)} in {len(unique_files)} file(s)")
    for e in err_lines[:10]:
        lines.append(f"  - `{e}`")
    lines.append("")

    # --- bandit ---
    lines.append("## bandit (security)")
    bandit_out_raw = _run(["bandit", "-r", "app/", "-f", "json"])
    # bandit may mix progress lines with json; strip leading non-json
    try:
        # find first '{'
        json_start = bandit_out_raw.index("{")
        json_str = bandit_out_raw[json_start:]
        data = json.loads(json_str)
        results = data.get("results", [])
        metrics = data.get("metrics", {}).get("_totals", {})
        lines.append(f"- **Total findings**: {len(results)}")
        lines.append(f"- **High confidence**: {metrics.get('CONFIDENCE.HIGH', 0)}")
        lines.append(f"- **Medium confidence**: {metrics.get('CONFIDENCE.MEDIUM', 0)}")
        lines.append(f"- **Low confidence**: {metrics.get('CONFIDENCE.LOW', 0)}")
        lines.append("")
        lines.append("### Top findings")
        for x in results[:10]:
            lines.append(f"- `{x['test_id']}`: {Path(x['filename']).relative_to(REPO)}:{x['line_number']} — {x['issue_text'][:80]}")
    except (ValueError, json.JSONDecodeError) as e:
        lines.append(f"- **Parse error**: {e}")
        lines.append(f"- **Raw output (first 200 chars)**: {bandit_out_raw[:200]}")
    lines.append("")

    # --- Summary ---
    lines.append("## Summary")
    lines.append("")
    lines.append("| Tool | Result | Action |")
    lines.append("|------|--------|--------|")
    lines.append(f"| ruff lint | {total_errs} occurrences across {n_errors} categories | `ruff check app/ --fix` (opt-in) |")
    lines.append(f"| ruff format | {n_unfmt} files need formatting | `ruff format app/` (opt-in) |")
    lines.append(f"| mypy | {len(err_lines)} errors in {len(unique_files)} files | Fix selectively (opt-in) |")
    bandit_n = len(results) if 'results' in dir() else '?'
    lines.append(f"| bandit | {bandit_n} findings | Review high-severity items (opt-in) |")
    lines.append("")
    lines.append("---")
    lines.append("*All baselines are informational. No code modifications required.*")

    # Write
    output = REPO / "docs" / "QUALITY_BASELINE_REPORT.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written to docs/QUALITY_BASELINE_REPORT.md")


if __name__ == "__main__":
    main()