"""Inject role-specific permissions and constraints into agent config files.

Each agent platform has a different config format:
- Claude Code: CLAUDE.md (natural language instructions)
- Cursor:      .cursorrules (natural language instructions)
- Codex:       AGENTS.md (natural language instructions)

This module writes a tagged block into each config file so the agent
understands its role constraints. The block is replaced on every
`harness prep --role X` call — idempotent, always current.
"""

import re
from pathlib import Path

HARNESS_DIR = None  # set by caller

BLOCK_START = "<!-- agent-harness:role:start -->"
BLOCK_END = "<!-- agent-harness:role:end -->"

AGENT_CONFIGS = ["CLAUDE.md", ".cursorrules", "AGENTS.md"]

SKILLS_BLOCK_START = "<!-- agent-harness:skills:start -->"
SKILLS_BLOCK_END = "<!-- agent-harness:skills:end -->"

# Maps each agent config file to the role whose skills it should reference.
# Claude Code = planner, Cursor = coder, Codex = reviewer.
_FILE_SKILL_ROLE = {
    "CLAUDE.md": "planner",
    ".cursorrules": "coder",
    "AGENTS.md": "reviewer",
}

_SKILLS_CONTENT = {
    "planner": (
        "## Agent Harness — Skills: planner\n\n"
        "At the start of every session, read and follow "
        "`.agent-harness/skills/planner/planner-start.md`.\n\n"
        "Additional skills available when needed:\n"
        "- Create a plan: `.agent-harness/skills/planner/create-plan.md`"
    ),
    "coder": (
        "## Agent Harness — Skills: coder\n\n"
        "At the start of every session, read and follow "
        "`.agent-harness/skills/coder/coder-start.md`.\n\n"
        "Additional skills available when needed:\n"
        "- Pick up a code review: `.agent-harness/skills/coder/pick-up-review.md`\n"
        "- Save a mistake to memory: `.agent-harness/skills/coder/save-mistake.md`\n"
        "- Query memory for context: `.agent-harness/skills/coder/query-memory.md`\n"
        "- Drill into a module map: `.agent-harness/skills/coder/drill-map.md`"
    ),
    "reviewer": (
        "## Agent Harness — Skills: reviewer\n\n"
        "At the start of every session, read and follow "
        "`.agent-harness/skills/reviewer/reviewer-start.md`.\n\n"
        "When your review is complete, read and follow "
        "`.agent-harness/skills/reviewer/leave-review.md`."
    ),
}


def _permission_lines(perms: dict) -> list[str]:
    lines = []
    if not perms.get("file_write", True):
        lines.append("- Do NOT modify or delete any existing code files.")
    if not perms.get("file_create", True):
        lines.append("- Do NOT create new files.")
    if not perms.get("git_commit", True):
        lines.append("- Do NOT run git commit.")
    if not perms.get("git_push", True):
        lines.append("- Do NOT run git push.")
    if not perms.get("install_deps", True):
        lines.append("- Do NOT install dependencies (npm install, pip install, etc.).")
    if not perms.get("shell_access", True):
        lines.append("- Do NOT execute shell commands.")
    return lines


def _tool_lines(tools: list, role_name: str) -> list[str]:
    if not tools:
        return []
    lines = ["", "Available harness commands for this role:"]
    tool_map = {
        "memory": "harness memory query \"<topic>\"   — retrieve relevant memories",
        "map": "harness map drill \"<module>\"      — get detailed module map",
        "mistakes": "harness mistakes <file>            — check known pitfalls",
        "test-results": "harness test-results [path]        — query test history",
        "rules": "harness rules check                — validate conventions",
    }
    for t in tools:
        if t in tool_map:
            lines.append(f"  {tool_map[t]}")
    return lines


def _build_block(role_name: str, role_cfg: dict) -> str:
    description = role_cfg.get("description", role_name)
    models = ", ".join(role_cfg.get("models", []))
    perms = role_cfg.get("permissions", {})
    tools = role_cfg.get("tools", [])

    lines = [
        BLOCK_START,
        f"## Agent Harness — Role: {role_name}",
        f"You are acting as the **{role_name}** ({description}).",
        f"Expected models: {models}" if models else "",
        "",
        "### Constraints",
    ]
    lines = [l for l in lines if l != ""]  # drop empty model line if no models

    perm_lines = _permission_lines(perms)
    if perm_lines:
        lines.extend(perm_lines)
    else:
        lines.append("- Full access — no restrictions for this role.")

    tool_section = _tool_lines(tools, role_name)
    lines.extend(tool_section)

    lines.extend([
        "",
        "Read `.agent-harness/context/bootstrap.md` for full project context.",
        BLOCK_END,
    ])

    return "\n".join(lines)


def _inject_block_into_file(file_path: Path, block: str, start_marker: str, end_marker: str):
    """Replace or append a tagged block in a config file."""
    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker),
        re.DOTALL,
    )
    if file_path.exists():
        content = file_path.read_text()
        if pattern.search(content):
            new_content = pattern.sub(block, content)
        else:
            new_content = content.rstrip() + "\n\n" + block + "\n"
    else:
        new_content = block + "\n"
    file_path.write_text(new_content)


def inject_role_permissions(role_name: str, role_cfg: dict, project_root: Path):
    """Write role constraints into all agent config files in project_root."""
    block = _build_block(role_name, role_cfg)
    for config_name in AGENT_CONFIGS:
        config_path = project_root / config_name
        _inject_block_into_file(config_path, block, BLOCK_START, BLOCK_END)


def inject_skills_block(project_root: Path):
    """Write role-specific skills references into each agent config file.

    CLAUDE.md    → planner skills
    .cursorrules → coder skills
    AGENTS.md    → reviewer skills
    """
    for config_name, role in _FILE_SKILL_ROLE.items():
        body = _SKILLS_CONTENT[role]
        block = f"{SKILLS_BLOCK_START}\n{body}\n{SKILLS_BLOCK_END}"
        _inject_block_into_file(project_root / config_name, block, SKILLS_BLOCK_START, SKILLS_BLOCK_END)
