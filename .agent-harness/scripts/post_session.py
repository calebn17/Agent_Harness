"""Capture session handoff after an agent session."""

from pathlib import Path
from scripts.common import HARNESS_DIR

HANDOFF_FILE = HARNESS_DIR / "context" / "session-handoff.md"


def capture_handoff():
    """Prompt the agent to write a handoff summary to session-handoff.md.

    In practice, the agent writes this file directly during the session.
    This script validates the file exists and is non-empty.
    """
    if not HANDOFF_FILE.exists() or not HANDOFF_FILE.read_text().strip():
        template = (
            "# Session Handoff\n\n"
            "## Worked On\n- \n\n"
            "## Decisions Made\n- \n\n"
            "## In Progress\n- \n\n"
            "## Blockers\n- \n"
        )
        HANDOFF_FILE.write_text(template)
        print(f"Created handoff template at {HANDOFF_FILE}")
        print("Fill it in before ending your session.")
    else:
        print(f"Handoff captured: {HANDOFF_FILE}")
