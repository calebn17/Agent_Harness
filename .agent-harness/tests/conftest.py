"""Shared fixtures for agent harness tests.

Each test gets an isolated temp directory with its own harness structure.
Module-level path constants (HARNESS_DIR, ENTRIES_DIR, etc.) are patched
via monkeypatch so no test touches the real harness data.
"""

import sys
import pytest
import yaml
from pathlib import Path

# Ensure scripts/ is importable when pytest runs from .agent-harness/
_harness_root = Path(__file__).parent.parent
if str(_harness_root) not in sys.path:
    sys.path.insert(0, str(_harness_root))

# Minimal config with low thresholds so threshold-boundary tests don't need 200 entries
MINIMAL_CONFIG = {
    "project": {"name": "test-project", "type": "python"},
    "budgets": {
        "bootstrap_chars": 500,
        "memory_query_max_entries": 5,
        "memory_query_full_chars": 500,
        "memory_query_brief_chars": 200,
        "map_drill_chars": 800,
    },
    "memory": {
        "max_entries": 5,
        "decay_default": 0.05,
        "decay_mistake": 0.02,
        "prune_threshold": 0.1,
        "access_bump": 0.3,
    },
    "tests": {
        "test_command": "pytest",
        "max_results": 5,
        "plan_location": "docs/plans/",
        "auto_rules_check": True,
    },
    "roles": {
        "planner": {
            "description": "Designs architecture and plans",
            "models": ["claude-opus"],
            "permissions": {
                "file_write": False,
                "file_create": True,
                "shell_access": True,
                "git_commit": False,
                "git_push": False,
                "install_deps": False,
            },
            "tools": ["memory", "map"],
            "bootstrap": {
                "sections": ["session_handoff", "diff_summary", "project_map", "conventions"],
                "mistake_categories": ["architecture", "process"],
                "map_detail": "expanded",
            },
        },
        "coder": {
            "description": "Writes and modifies code",
            "models": ["claude-sonnet", "cursor-composer2"],
            "permissions": {
                "file_write": True,
                "file_create": True,
                "shell_access": True,
                "git_commit": True,
                "git_push": False,
                "install_deps": False,
            },
            "tools": ["memory", "map", "mistakes", "test-results", "rules"],
            "bootstrap": {
                "sections": ["session_handoff", "diff_summary", "project_map", "active_mistakes", "conventions"],
                "mistake_categories": ["pattern", "architecture"],
            },
        },
        "reviewer": {
            "description": "Reviews code for correctness and conventions",
            "models": ["codex"],
            "permissions": {
                "file_write": True,
                "file_create": False,
                "shell_access": True,
                "git_commit": False,
                "git_push": False,
                "install_deps": False,
            },
            "tools": ["memory", "mistakes", "test-results", "rules"],
            "bootstrap": {
                "sections": ["session_handoff", "diff_summary", "active_mistakes", "conventions"],
                "mistake_categories": ["pattern", "process", "architecture"],
                "conventions_detail": "expanded",
            },
        },
    },
}


@pytest.fixture()
def harness_env(tmp_path, monkeypatch):
    """Isolated harness environment in a temp directory.

    Patches all module-level path constants so scripts read/write to tmp_path
    instead of the real harness directory.
    """
    harness_dir = tmp_path / ".agent-harness"
    project_root = tmp_path / "project"

    # Create directory structure
    (harness_dir / "memory" / "entries").mkdir(parents=True)
    (harness_dir / "logs").mkdir(parents=True)
    (harness_dir / "context" / "detail").mkdir(parents=True)
    (harness_dir / "rules").mkdir(parents=True)
    project_root.mkdir()

    (harness_dir / "config.yaml").write_text(yaml.dump(MINIMAL_CONFIG))
    (harness_dir / "memory" / "index.yaml").write_text("entries: []\n")

    # --- Patch scripts.common ---
    import scripts.common as common_mod
    monkeypatch.setattr(common_mod, "HARNESS_DIR", harness_dir)
    monkeypatch.setattr(common_mod, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(common_mod, "LOCK_FILE", harness_dir / ".lock")
    monkeypatch.setattr(common_mod, "CONFIG_FILE", harness_dir / "config.yaml")
    monkeypatch.setattr(common_mod, "_config_cache", None)

    # --- Patch scripts.memory ---
    import scripts.memory as memory_mod
    monkeypatch.setattr(memory_mod, "HARNESS_DIR", harness_dir)
    monkeypatch.setattr(memory_mod, "ENTRIES_DIR", harness_dir / "memory" / "entries")

    # --- Patch scripts.prune ---
    import scripts.prune as prune_mod
    monkeypatch.setattr(prune_mod, "HARNESS_DIR", harness_dir)
    monkeypatch.setattr(prune_mod, "ENTRIES_DIR", harness_dir / "memory" / "entries")
    monkeypatch.setattr(prune_mod, "TEST_RESULTS", harness_dir / "logs" / "test-results.jsonl")

    # --- Patch scripts.gen_bootstrap (all module-level derived paths) ---
    import scripts.gen_bootstrap as bootstrap_mod
    context_dir = harness_dir / "context"
    monkeypatch.setattr(bootstrap_mod, "HARNESS_DIR", harness_dir)
    monkeypatch.setattr(bootstrap_mod, "CONTEXT_DIR", context_dir)
    monkeypatch.setattr(bootstrap_mod, "BOOTSTRAP_FILE", context_dir / "bootstrap.md")
    monkeypatch.setattr(bootstrap_mod, "HASH_FILE", context_dir / ".bootstrap-hash")
    monkeypatch.setattr(bootstrap_mod, "HANDOFF_FILE", context_dir / "session-handoff.md")
    monkeypatch.setattr(bootstrap_mod, "MAP_DETAIL_DIR", context_dir / "detail")
    monkeypatch.setattr(bootstrap_mod, "CONVENTIONS_FILE", harness_dir / "rules" / "conventions.yaml")
    monkeypatch.setattr(bootstrap_mod, "MEMORY_INDEX", harness_dir / "memory" / "index.yaml")

    return {"harness_dir": harness_dir, "project_root": project_root}
