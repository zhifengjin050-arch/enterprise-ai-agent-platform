#!/usr/bin/env python3
"""Parse bandit JSON output from stdin."""

import json
import sys

data = json.load(sys.stdin)
results = data.get("results", [])
metrics = data.get("metrics", {}).get("_totals", {})
print(f"Total findings: {len(results)}")
print(
    f"High: {metrics.get('CONFIDENCE.HIGH', 0)}, Medium: {metrics.get('CONFIDENCE.MEDIUM', 0)}, Low: {metrics.get('CONFIDENCE.LOW', 0)}"
)
for x in results[:15]:
    print(f"  - {x['test_id']}: {x['filename']}:{x['line_number']} {x['issue_text'][:80]}")
