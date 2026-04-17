"""End-to-end CLI tests.

These run the actual `harness` CLI in a subprocess against a temp project.
They verify that commands route correctly and produce the right file outputs —
not re-testing the individual behaviors already covered by unit tests.
"""

import shutil
import subprocess
import sys
import yaml
from pathlib import Path

HARNESS_SOURCE = Path(__file__).parent.parent  # .agent-harness/

# Same minimal config as conftest, kept local to avoid import coupling
_MINIMAL_CONFIG = {
    "project": {"name": "integration-test", "type": "python"},
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
                "file_write": False, "file_create": True, "shell_access": True,
                "git_commit": False, "git_push": False, "install_deps": False,
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
                "file_write": True, "file_create": True, "shell_access": True,
                "git_commit": True, "git_push": False, "install_deps": False,
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
                "file_write": True, "file_create": False, "shell_access": True,
                "git_commit": False, "git_push": False, "install_deps": False,
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


def _setup_project(tmp_path):
    """Copy harness scripts into a temp project with clean state."""
    project_dir = tmp_path / "project"
    harness_dir = project_dir / ".agent-harness"

    # Copy only the code — not context/, memory/, logs/ which have state
    for item in ["harness", "scripts"]:
        src = HARNESS_SOURCE / item
        dst = harness_dir / item
        if src.is_dir():
            shutil.copytree(str(src), str(dst),
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))

    # Make harness CLI executable
    (harness_dir / "harness").chmod(0o755)

    # Fresh state directories
    (harness_dir / "memory" / "entries").mkdir(parents=True)
    (harness_dir / "logs").mkdir(parents=True)
    (harness_dir / "context" / "detail").mkdir(parents=True)
    (harness_dir / "rules").mkdir(parents=True)

    (harness_dir / "config.yaml").write_text(yaml.dump(_MINIMAL_CONFIG))
    (harness_dir / "memory" / "index.yaml").write_text("entries: []\n")

    return project_dir, harness_dir


def _run(project_dir, *args):
    return subprocess.run(
        [sys.executable, ".agent-harness/harness"] + list(args),
        cwd=str(project_dir),
        capture_output=True, text=True,
    )


# --- prep ---

def test_prep_exits_zero(tmp_path):
    project_dir, _ = _setup_project(tmp_path)
    result = _run(project_dir, "prep", "--role", "coder")
    assert result.returncode == 0, result.stderr


def test_prep_creates_bootstrap(tmp_path):
    project_dir, harness_dir = _setup_project(tmp_path)
    _run(project_dir, "prep", "--role", "coder")
    assert (harness_dir / "context" / "bootstrap.md").exists()


def test_prep_injects_planner_role_block(tmp_path):
    project_dir, _ = _setup_project(tmp_path)
    _run(project_dir, "prep", "--role", "planner")
    content = (project_dir / "CLAUDE.md").read_text()
    assert "planner" in content
    assert "Do NOT modify or delete any existing code files" in content


def test_prep_role_switch_replaces_block(tmp_path):
    project_dir, _ = _setup_project(tmp_path)
    _run(project_dir, "prep", "--role", "planner")
    _run(project_dir, "prep", "--role", "coder")
    content = (project_dir / "CLAUDE.md").read_text()
    assert content.count("<!-- agent-harness:role:start -->") == 1
    block_body = content.split("<!-- agent-harness:role:start -->")[1]
    assert "coder" in block_body
    assert "planner" not in block_body


def test_prep_skip_if_unchanged(tmp_path):
    project_dir, _ = _setup_project(tmp_path)
    _run(project_dir, "prep", "--role", "coder")
    result = _run(project_dir, "prep", "--role", "coder")
    assert "unchanged" in result.stdout.lower()


def test_prep_all_agent_configs_written(tmp_path):
    project_dir, _ = _setup_project(tmp_path)
    _run(project_dir, "prep", "--role", "reviewer")
    for name in ["CLAUDE.md", ".cursorrules", "AGENTS.md"]:
        path = project_dir / name
        assert path.exists(), f"{name} not created"
        assert "<!-- agent-harness:role:start -->" in path.read_text()


# --- memory ---

def test_memory_save_exits_zero(tmp_path):
    project_dir, _ = _setup_project(tmp_path)
    result = _run(project_dir, "memory", "save", "--category", "pattern",
                  "Use async/await for all I/O operations")
    assert result.returncode == 0, result.stderr


def test_memory_save_and_query(tmp_path):
    project_dir, _ = _setup_project(tmp_path)
    _run(project_dir, "memory", "save", "--category", "pattern",
         "Use async/await for all I/O operations")
    result = _run(project_dir, "memory", "query", "async")
    assert result.returncode == 0
    assert "mem-001" in result.stdout


def test_memory_query_no_results(tmp_path):
    project_dir, _ = _setup_project(tmp_path)
    result = _run(project_dir, "memory", "query", "zymurgical nonsense")
    assert result.returncode == 0
    assert "No matching" in result.stdout


def test_memory_forget(tmp_path):
    project_dir, harness_dir = _setup_project(tmp_path)
    _run(project_dir, "memory", "save", "--category", "pattern", "First entry")
    result = _run(project_dir, "memory", "forget", "mem-001")
    assert result.returncode == 0
    index = yaml.safe_load((harness_dir / "memory" / "index.yaml").read_text())
    assert len(index["entries"]) == 0
