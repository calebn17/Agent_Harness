"""Convention rules checker."""

import fnmatch
import re
import subprocess
from pathlib import Path

import yaml

from scripts.common import HARNESS_DIR, PROJECT_ROOT

CONVENTIONS_FILE = HARNESS_DIR / "rules" / "conventions.yaml"

# Simple pattern-based checks: rule id -> (pattern, match_means_violation)
BUILT_IN_CHECKS = {
    "no-console-log": (r"\bconsole\.log\b", True),
    "no-relative-imports": (r"^from \.\.", True),
    "no-unittest": (r"import unittest\b", True),
}


def _get_staged_files() -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), "diff", "--cached", "--name-only", "--diff-filter=AM"],
        capture_output=True, text=True
    )
    return [PROJECT_ROOT / f for f in result.stdout.strip().splitlines() if f]


def _get_changed_files() -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), "diff", "--name-only", "--diff-filter=AM"],
        capture_output=True, text=True
    )
    return [PROJECT_ROOT / f for f in result.stdout.strip().splitlines() if f]


def _check_file(file_path: Path, rules: list) -> list[str]:
    violations = []
    if not file_path.exists():
        return violations

    try:
        content = file_path.read_text(errors="ignore")
        lines = content.splitlines()
    except Exception:
        return violations

    rel_path = str(file_path.relative_to(PROJECT_ROOT))

    for rule in rules:
        rule_id = rule.get("id", "")
        scope = rule.get("scope", "*")
        rule_text = rule.get("rule", "")
        severity = rule.get("severity", "error").upper()

        # Check scope match
        if not fnmatch.fnmatch(rel_path, scope):
            continue

        # Built-in pattern checks
        if rule_id in BUILT_IN_CHECKS:
            pattern, violation_on_match = BUILT_IN_CHECKS[rule_id]
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    violations.append(
                        f"[{severity}] {rel_path}:{i} — {rule_text}"
                    )
                    break  # one violation per rule per file is enough

    return violations


def rules_check(files: list | None = None, staged: bool = False):
    if not CONVENTIONS_FILE.exists():
        print("No conventions.yaml found. Create rules/conventions.yaml first.")
        return

    with open(CONVENTIONS_FILE) as f:
        data = yaml.safe_load(f)
    rules = data.get("rules", [])

    if not rules:
        print("No rules defined in conventions.yaml.")
        return

    # Determine which files to check
    if files:
        check_paths = [PROJECT_ROOT / f for f in files]
    elif staged:
        check_paths = _get_staged_files()
    else:
        check_paths = _get_changed_files()

    if not check_paths:
        print("No files to check.")
        return

    all_violations = []
    for path in check_paths:
        all_violations.extend(_check_file(path, rules))

    if all_violations:
        for v in all_violations:
            print(v)
        print(f"\n{len(all_violations)} violation(s) found.")
    else:
        print(f"All clear — {len(check_paths)} file(s) checked.")
