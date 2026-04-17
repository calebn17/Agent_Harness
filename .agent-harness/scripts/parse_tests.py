"""Parse test output into structured results stored in logs/test-results.jsonl."""

import fcntl
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from scripts.common import HARNESS_DIR, acquire_lock, release_lock

TEST_RESULTS = HARNESS_DIR / "logs" / "test-results.jsonl"


def _parse_pytest(output: str) -> dict:
    """Parse pytest output into a structured result."""
    passed = len(re.findall(r" passed", output))
    failed = len(re.findall(r" failed", output))
    errors = len(re.findall(r" error", output, re.IGNORECASE))

    # Extract failure details
    failures = []
    # Match FAILED test::name lines
    for match in re.finditer(r"FAILED (.+?) - (.+)", output):
        failures.append({"test": match.group(1).strip(), "reason": match.group(2).strip()})

    # Fallback: match "AssertionError" or "Error" blocks
    if not failures:
        for match in re.finditer(r"(FAILED|ERROR)\s+(.+)", output):
            failures.append({"test": match.group(2).strip(), "reason": "see output"})

    status = "pass" if failed == 0 and errors == 0 else "fail"
    return {
        "runner": "pytest",
        "status": status,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "failures": failures[:10],  # cap stored failures
    }


def _parse_jest(output: str) -> dict:
    passed = len(re.findall(r"✓|✔|PASS", output))
    failed = len(re.findall(r"✕|✗|FAIL", output))
    failures = []
    for match in re.finditer(r"● (.+)", output):
        failures.append({"test": match.group(1).strip(), "reason": "see output"})
    status = "pass" if failed == 0 else "fail"
    return {
        "runner": "jest",
        "status": status,
        "passed": passed,
        "failed": failed,
        "failures": failures[:10],
    }


def _parse_xcode(output: str) -> dict:
    passed = len(re.findall(r"Test Case .+ passed", output))
    failed = len(re.findall(r"Test Case .+ failed", output))
    failures = []
    for match in re.finditer(r"Test Case '(.+?)'.+failed", output):
        failures.append({"test": match.group(1).strip(), "reason": "see output"})
    status = "pass" if failed == 0 else "fail"
    return {
        "runner": "xcode",
        "status": status,
        "passed": passed,
        "failed": failed,
        "failures": failures[:10],
    }


def _detect_and_parse(output: str) -> dict:
    if "pytest" in output or "collected" in output:
        return _parse_pytest(output)
    elif "jest" in output.lower() or "PASS\n" in output or "FAIL\n" in output:
        return _parse_jest(output)
    elif "Test Case" in output or "XCTest" in output:
        return _parse_xcode(output)
    else:
        # Generic: look for pass/fail keywords
        status = "pass" if re.search(r"\bpass(ed)?\b", output, re.IGNORECASE) else "fail"
        return {"runner": "unknown", "status": status, "failures": []}


def _append_result(result: dict):
    TEST_RESULTS.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.utcnow().isoformat(),
        **result,
    }
    lock = acquire_lock()
    try:
        with open(TEST_RESULTS, "a") as f:
            f.write(json.dumps(record) + "\n")
    finally:
        release_lock(lock)


def parse_stdin():
    """Read test output from stdin and append structured result."""
    output = sys.stdin.read()
    result = _detect_and_parse(output)
    _append_result(result)
    status_str = result.get("status", "unknown").upper()
    failed = result.get("failed", 0)
    passed = result.get("passed", 0)
    print(f"[{status_str}] passed={passed} failed={failed}")
    if result.get("failures"):
        for f in result["failures"][:5]:
            print(f"  FAILED: {f['test']}")


def parse_output(output: str):
    result = _detect_and_parse(output)
    _append_result(result)
    return result
