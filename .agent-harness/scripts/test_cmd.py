"""harness test and harness test-results commands."""

import json
import subprocess
from pathlib import Path
from typing import Optional

from scripts.common import HARNESS_DIR, PROJECT_ROOT, load_config
from scripts.parse_tests import parse_output

TEST_RESULTS = HARNESS_DIR / "logs" / "test-results.jsonl"


def run_tests():
    cfg = load_config()
    cmd = cfg.get("tests", {}).get("test_command", "pytest")
    print(f"Running: {cmd}")
    result = subprocess.run(
        cmd, shell=True, cwd=PROJECT_ROOT, capture_output=True, text=True
    )
    combined = result.stdout + result.stderr
    print(combined)
    parsed = parse_output(combined)
    return parsed


def query_results(path: Optional[str] = None):
    if not TEST_RESULTS.exists():
        print("No test results stored yet.")
        return

    lines = TEST_RESULTS.read_text().strip().splitlines()
    records = []
    for line in lines:
        try:
            r = json.loads(line)
            records.append(r)
        except json.JSONDecodeError:
            continue

    # Filter by path if specified
    if path:
        records = [
            r for r in records
            if any(path in f.get("test", "") for f in r.get("failures", []))
            or path in str(r)
        ]

    # Show last 5
    for r in records[-5:]:
        ts = r.get("ts", "")[:16]
        status = r.get("status", "?").upper()
        runner = r.get("runner", "?")
        passed = r.get("passed", 0)
        failed = r.get("failed", 0)
        print(f"[{ts}] {status} ({runner}) — passed={passed} failed={failed}")
        for f in r.get("failures", [])[:3]:
            print(f"  FAILED: {f.get('test', '?')} — {f.get('reason', '')}")
