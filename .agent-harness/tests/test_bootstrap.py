"""Tests for gen_bootstrap.py: char budget, skip-if-unchanged, role section filtering."""

import pytest
from scripts.gen_bootstrap import generate_bootstrap


# --- basic generation ---

def test_bootstrap_file_created(harness_env):
    harness_dir = harness_env["harness_dir"]
    generate_bootstrap(role="coder")
    assert (harness_dir / "context" / "bootstrap.md").exists()


def test_bootstrap_not_empty(harness_env):
    harness_dir = harness_env["harness_dir"]
    generate_bootstrap(role="coder")
    content = (harness_dir / "context" / "bootstrap.md").read_text()
    assert len(content.strip()) > 0


def test_hash_file_written(harness_env):
    harness_dir = harness_env["harness_dir"]
    generate_bootstrap(role="coder")
    assert (harness_dir / "context" / ".bootstrap-hash").exists()


# --- char budget ---

def test_char_budget_enforced(harness_env):
    """Bootstrap must not exceed bootstrap_chars (500 in test config) by more than
    the truncation message overhead (~50 chars)."""
    harness_dir = harness_env["harness_dir"]
    # Write a huge project map to force truncation
    (harness_dir / "context" / "detail" / "map-root.md").write_text("x" * 10_000)
    generate_bootstrap(role="coder")
    content = (harness_dir / "context" / "bootstrap.md").read_text()
    assert len(content) <= 560  # 500 budget + truncation message


def test_truncation_message_present_when_over_budget(harness_env):
    harness_dir = harness_env["harness_dir"]
    (harness_dir / "context" / "detail" / "map-root.md").write_text("x" * 10_000)
    generate_bootstrap(role="coder")
    content = (harness_dir / "context" / "bootstrap.md").read_text()
    assert "truncated" in content


# --- skip-if-unchanged ---

def test_second_call_skips_regeneration(harness_env, capsys):
    generate_bootstrap(role="coder")
    capsys.readouterr()  # discard first-run output

    generate_bootstrap(role="coder")
    out = capsys.readouterr().out
    assert "unchanged" in out.lower()


def test_different_role_triggers_regeneration(harness_env, capsys):
    generate_bootstrap(role="coder")
    capsys.readouterr()

    generate_bootstrap(role="reviewer")
    out = capsys.readouterr().out
    assert "unchanged" not in out.lower()


# --- role section filtering ---

def test_role_header_in_bootstrap(harness_env):
    harness_dir = harness_env["harness_dir"]
    generate_bootstrap(role="reviewer")
    content = (harness_dir / "context" / "bootstrap.md").read_text()
    assert "reviewer" in content.lower()


def test_reviewer_excludes_project_map_section(harness_env):
    """reviewer bootstrap config has no project_map in its sections list."""
    harness_dir = harness_env["harness_dir"]
    (harness_dir / "context" / "detail" / "map-root.md").write_text("- src/ [Python] — 10 files")
    generate_bootstrap(role="reviewer")
    content = (harness_dir / "context" / "bootstrap.md").read_text()
    assert "## Project Map" not in content


def test_coder_includes_project_map_section(harness_env):
    harness_dir = harness_env["harness_dir"]
    (harness_dir / "context" / "detail" / "map-root.md").write_text("- src/ [Python] — 10 files")
    generate_bootstrap(role="coder")
    content = (harness_dir / "context" / "bootstrap.md").read_text()
    assert "## Project Map" in content


def test_active_mistakes_always_included_in_mistake_category(harness_env):
    """Even if mistake category isn't listed in role config, it's always surfaced."""
    import yaml
    from datetime import date
    harness_dir = harness_env["harness_dir"]
    index = {
        "entries": [{
            "id": "mem-001", "category": "mistake",
            "summary": "Never use eval() in user input handlers",
            "relevance": 0.9, "files": [],
            "created": date.today().isoformat(),
            "last_relevant": date.today().isoformat(),
        }]
    }
    (harness_dir / "memory" / "index.yaml").write_text(yaml.dump(index))
    generate_bootstrap(role="coder")
    content = (harness_dir / "context" / "bootstrap.md").read_text()
    assert "mem-001" in content


# --- worktree path ---

def test_worktree_bootstrap_written_to_worktree(harness_env, tmp_path):
    worktree_dir = tmp_path / "worktree"
    worktree_dir.mkdir()
    generate_bootstrap(role="coder", worktree=str(worktree_dir))
    bootstrap = worktree_dir / ".agent-harness" / "context" / "bootstrap.md"
    assert bootstrap.exists()
