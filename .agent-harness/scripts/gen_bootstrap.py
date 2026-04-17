"""Generate context/bootstrap.md — the always-loaded agent context file."""

import hashlib
import subprocess
from datetime import date, datetime
from pathlib import Path

from scripts.common import (
    HARNESS_DIR, PROJECT_ROOT, load_config, load_memory_index,
)

CONTEXT_DIR = HARNESS_DIR / "context"
BOOTSTRAP_FILE = CONTEXT_DIR / "bootstrap.md"
HASH_FILE = CONTEXT_DIR / ".bootstrap-hash"
HANDOFF_FILE = CONTEXT_DIR / "session-handoff.md"
MAP_DETAIL_DIR = CONTEXT_DIR / "detail"
CONVENTIONS_FILE = HARNESS_DIR / "rules" / "conventions.yaml"
MEMORY_INDEX = HARNESS_DIR / "memory" / "index.yaml"


def _git(cmd: list) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT)] + cmd,
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _compute_input_hash(role: str) -> str:
    h = hashlib.md5()
    h.update(role.encode())
    h.update(_git(["rev-parse", "HEAD"]).encode())
    for path in [HANDOFF_FILE, CONVENTIONS_FILE, MEMORY_INDEX]:
        if path.exists():
            h.update(str(path.stat().st_mtime).encode())
    if MAP_DETAIL_DIR.exists():
        for f in sorted(MAP_DETAIL_DIR.glob("*.md")):
            h.update(str(f.stat().st_mtime).encode())
    return h.hexdigest()


def _get_role_config(role: str) -> dict:
    cfg = load_config()
    roles = cfg.get("roles", {})
    return roles.get(role, roles.get("coder", {}))


def _section_session_handoff(char_budget: int) -> str:
    if not HANDOFF_FILE.exists():
        return ""
    content = HANDOFF_FILE.read_text().strip()
    if len(content) > char_budget:
        content = content[:char_budget] + " [more: harness post]"
    return f"## Last Session\n{content}\n"


def _section_diff_summary(char_budget: int) -> str:
    # Get git log since last session timestamp
    log = _git(["log", "--oneline", "-10", "--name-only", "--diff-filter=AM"])
    if not log:
        return ""
    if len(log) > char_budget:
        lines = log.splitlines()
        trimmed = []
        total = 0
        for line in lines:
            if total + len(line) > char_budget:
                trimmed.append(f"[more: git log --oneline]")
                break
            trimmed.append(line)
            total += len(line)
        log = "\n".join(trimmed)
    return f"## Since Last Session\n{log}\n"


def _section_project_map(char_budget: int, map_detail: str = "normal") -> str:
    # Look for a top-level map file
    map_root = MAP_DETAIL_DIR / "map-root.md"
    if not map_root.exists():
        return ""
    content = map_root.read_text().strip()
    if map_detail == "expanded":
        char_budget = int(char_budget * 1.5)
    if len(content) > char_budget:
        content = content[:char_budget] + " [more: harness map drill <module>]"
    return f"## Project Map\n{content}\n"


def _compute_confidence(module_path: str) -> float:
    """Inline confidence scoring: git touch history + mistake count."""
    log = _git(["log", "--oneline", "--", module_path])
    sessions_touched = len(log.splitlines()) if log else 0
    base_familiarity = min(sessions_touched / 10, 1.0)

    # Recency: days since last touch
    last_date_str = _git(["log", "-1", "--format=%ad", "--date=short", "--", module_path])
    days_since = 0
    if last_date_str:
        try:
            last = date.fromisoformat(last_date_str)
            days_since = (date.today() - last).days
        except ValueError:
            pass
    recency_multiplier = max(1.0 - (days_since * 0.03), 0.2)

    # Mistake penalty: count mistake memories for this path
    index = load_memory_index()
    mistakes = sum(
        1 for e in index.get("entries", [])
        if e.get("category") == "mistake"
        and any(module_path in f or f in module_path for f in e.get("files", []))
    )
    mistake_penalty = min(mistakes * 0.1, 0.5)

    return base_familiarity * recency_multiplier * (1 - mistake_penalty)


def _section_active_mistakes(char_budget: int, categories: list) -> str:
    index = load_memory_index()
    entries = index.get("entries", [])

    # Always include "mistake" category plus whatever role specifies
    all_categories = list(set(categories) | {"mistake"})

    # Filter to mistake categories, sort by relevance
    mistakes = [
        e for e in entries
        if e.get("category") in all_categories and e.get("relevance", 0) > 0.1
    ]
    mistakes.sort(key=lambda e: e.get("relevance", 0), reverse=True)
    top = mistakes[:5]

    if not top:
        return ""

    lines = ["## Active Mistakes"]
    total_chars = len(lines[0])
    for e in top:
        line = f"- [{e['id']}] {e.get('summary', '')}"
        if total_chars + len(line) > char_budget:
            lines.append("[more: harness mistakes for <file>]")
            break
        lines.append(line)
        total_chars += len(line)
    return "\n".join(lines) + "\n"


def _section_conventions(char_budget: int, detail: str = "normal") -> str:
    if not CONVENTIONS_FILE.exists():
        return ""
    import yaml
    with open(CONVENTIONS_FILE) as f:
        data = yaml.safe_load(f)
    rules = data.get("rules", [])
    if detail != "expanded":
        rules = rules[:8]  # top 8 only

    lines = ["## Conventions"]
    total = len(lines[0])
    for r in rules:
        sev = r.get("severity", "error").upper()
        line = f"- [{sev}] {r.get('rule', '')} (scope: {r.get('scope', '*')})"
        if total + len(line) > char_budget:
            lines.append("[more: rules/conventions.yaml]")
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines) + "\n"


def _section_commands(role_cfg: dict) -> str:
    tools = role_cfg.get("tools", [])
    if not tools:
        return ""
    cmds = []
    tool_map = {
        "memory": 'harness memory query "<topic>"',
        "map": 'harness map drill "<module>"',
        "mistakes": 'harness mistakes <file>',
        "test-results": 'harness test-results [path]',
        "rules": 'harness rules check',
    }
    for t in tools:
        if t in tool_map:
            cmds.append(f"- {tool_map[t]}")
    if not cmds:
        return ""
    return "## Commands\n" + "\n".join(cmds) + "\n"


def generate_bootstrap(role: str = "coder", worktree: str | None = None):
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

    cfg = load_config()
    role_cfg = _get_role_config(role)
    target_root = Path(worktree) if worktree else PROJECT_ROOT

    # Always inject role permissions into agent config files (fast, idempotent)
    from scripts.permissions import inject_role_permissions
    inject_role_permissions(role, role_cfg, target_root)

    input_hash = _compute_input_hash(role)

    # Skip bootstrap assembly if inputs unchanged
    if HASH_FILE.exists() and HASH_FILE.read_text().strip() == input_hash:
        print("Bootstrap unchanged — skipping regeneration.")
        return

    budgets = cfg.get("budgets", {})
    total_budget = budgets.get("bootstrap_chars", 2000)

    bootstrap_cfg = role_cfg.get("bootstrap", {})
    sections = bootstrap_cfg.get("sections", [
        "session_handoff", "diff_summary", "project_map", "active_mistakes", "conventions"
    ])
    mistake_categories = bootstrap_cfg.get("mistake_categories", ["pattern", "architecture", "mistake"])
    map_detail = bootstrap_cfg.get("map_detail", "normal")
    conventions_detail = bootstrap_cfg.get("conventions_detail", "normal")

    # Character budgets per section (proportional to total)
    section_budgets = {
        "session_handoff": 400,
        "diff_summary": 300,
        "project_map": 500,
        "active_mistakes": 300,
        "conventions": 200,
    }

    parts = []

    # Header
    role_desc = role_cfg.get("description", role)
    models = ", ".join(role_cfg.get("models", []))
    header = f"# Harness Context — Role: {role}\n{role_desc} ({models})\n"
    parts.append(header)

    if "session_handoff" in sections:
        s = _section_session_handoff(section_budgets["session_handoff"])
        if s:
            parts.append(s)

    if "diff_summary" in sections:
        s = _section_diff_summary(section_budgets["diff_summary"])
        if s:
            parts.append(s)

    if "project_map" in sections:
        s = _section_project_map(section_budgets["project_map"], map_detail)
        if s:
            parts.append(s)

    if "active_mistakes" in sections:
        s = _section_active_mistakes(section_budgets["active_mistakes"], mistake_categories)
        if s:
            parts.append(s)

    if "conventions" in sections:
        s = _section_conventions(section_budgets["conventions"], conventions_detail)
        if s:
            parts.append(s)

    # Available commands
    cmd_section = _section_commands(role_cfg)
    if cmd_section:
        parts.append(cmd_section)

    content = "\n".join(parts)

    # Hard cap enforcement
    if len(content) > total_budget:
        content = content[:total_budget] + "\n[bootstrap truncated at budget]"

    # Write to worktree or default location
    if worktree:
        out_path = Path(worktree) / ".agent-harness" / "context" / "bootstrap.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_path = BOOTSTRAP_FILE

    out_path.write_text(content)
    HASH_FILE.write_text(input_hash)
    print(f"Bootstrap generated ({len(content)} chars) → {out_path}")
