"""Generate a session handoff doc from the latest git commit.

Called automatically by the post-commit hook after every commit.
The coder-start skill reads, ingests, and deletes this file.
"""

import subprocess
from pathlib import Path

from scripts.common import HARNESS_DIR

HANDOFF_DIR = HARNESS_DIR / "handoff"
HANDOFF_FILE = HANDOFF_DIR / "handoff.md"


def generate_handoff():
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)

    project_root = HARNESS_DIR.parent

    commit_msg = subprocess.check_output(
        ["git", "log", "-1", "--pretty=%B"],
        text=True,
        cwd=project_root,
    ).strip()

    changed_files = subprocess.check_output(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        text=True,
        cwd=project_root,
    ).strip()

    diff_stat = subprocess.check_output(
        ["git", "diff-tree", "--no-commit-id", "--stat", "-r", "HEAD"],
        text=True,
        cwd=project_root,
    ).strip()

    content = (
        "# Session Handoff\n\n"
        f"## Last Commit\n{commit_msg}\n\n"
        f"## Changed Files\n{changed_files}\n\n"
        f"## Diff Summary\n{diff_stat}\n"
    )
    HANDOFF_FILE.write_text(content)


if __name__ == "__main__":
    generate_handoff()
