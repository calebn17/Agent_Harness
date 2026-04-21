"""Capture session handoff after an agent session."""

from pathlib import Path
from scripts.common import HARNESS_DIR

HANDOFF_FILE = HARNESS_DIR / "context" / "session-handoff.md"


def capture_handoff():
    """Deprecated: handoff is now generated automatically by the post-commit hook.

    This command is kept for backwards compatibility. The post-commit hook
    writes .agent-harness/handoff/handoff.md after every commit, and
    coder-start.md ingests and deletes it automatically.
    """
    print(
        "Note: 'harness post' is deprecated. The post-commit hook now generates "
        "the handoff automatically after each commit. "
        "See .agent-harness/handoff/handoff.md if a handoff was recently written."
    )
