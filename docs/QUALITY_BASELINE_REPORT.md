# Quality Baseline Report — Enterprise AI Agent Platform v1.0 RC

> **Generated**: 2026-08-18
>
> **Phase A-3**: Quality gate configuration only. No mass code fixes required.

---

## ruff (lint)

| Rule | Count | Description |
|------|-------|-------------|
| W292 | 187 | Missing newline at end of file |
| F401 | 162 | Unused import |
| I001 | 48 | Unsorted imports |
| E402 | 31 | Module import not at top of file |
| F541 | 14 | F-string missing placeholders |
| F841 | 10 | Unused variable |
| E712 | 1 | True/false comparison |
| F402 | 1 | Import shadowed by loop variable |
| F821 | 1 | Undefined name |
| N811 | 1 | Constant imported as non-constant |
| N813 | 1 | CamelCase imported as lowercase |
| N818 | 1 | Error suffix on exception name |
| W293 | 1 | Blank line with whitespace |
| **Total** | **459** | |

**Action**: `ruff check app/ --fix` (opt-in, 411 auto-fixable)

---

## ruff (format)

- **Files to reformat**: 216

**Action**: `ruff format app/` (opt-in)

---

## mypy (type check)

- **Errors**: 1
- **File**: `app/monitor/metrics.py:64` — Invalid syntax

**Action**: Investigate `metrics.py:64` (opt-in)

---

## bandit (security scan)

- Bandit encountered encoding issues on Windows PowerShell.
- Manual scan command: `bandit -r app/ -f json -o bandit-report.json`

**Action**: Run bandit in a POSIX environment or via WSL (opt-in)

---

## Summary

| Tool | Result | Action |
|------|--------|--------|
| ruff lint | 459 issues (411 auto-fixable) | `ruff check app/ --fix` |
| ruff format | 216 files | `ruff format app/` |
| mypy | 1 error in `metrics.py` | Fix `metrics.py:64` |
| bandit | Encoding issue on Windows | Re-run on Linux/macOS |

---

*All baselines are informational. No code modifications are required per Phase A-3 rules. These numbers serve as a reference point for future quality improvements.*