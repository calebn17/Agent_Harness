"""Tests for permissions.py: role block injection into agent config files."""

from scripts.permissions import inject_role_permissions, BLOCK_START, BLOCK_END

PLANNER_CFG = {
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
}

CODER_CFG = {
    "description": "Writes and modifies code",
    "models": ["claude-sonnet"],
    "permissions": {
        "file_write": True,
        "file_create": True,
        "shell_access": True,
        "git_commit": True,
        "git_push": False,
        "install_deps": False,
    },
    "tools": ["memory", "map", "mistakes", "test-results", "rules"],
}


# --- file creation ---

def test_creates_config_files_when_missing(tmp_path):
    inject_role_permissions("planner", PLANNER_CFG, tmp_path)
    for name in ["CLAUDE.md", ".cursorrules", "AGENTS.md"]:
        assert (tmp_path / name).exists(), f"{name} was not created"


def test_block_present_in_new_file(tmp_path):
    inject_role_permissions("planner", PLANNER_CFG, tmp_path)
    content = (tmp_path / "CLAUDE.md").read_text()
    assert BLOCK_START in content
    assert BLOCK_END in content


def test_appends_block_to_existing_file(tmp_path):
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("Read bootstrap.md before each task.\n")
    inject_role_permissions("planner", PLANNER_CFG, tmp_path)
    content = claude_md.read_text()
    assert "Read bootstrap.md before each task." in content
    assert BLOCK_START in content


# --- block replacement (role switch) ---

def test_block_replaced_on_role_switch(tmp_path):
    inject_role_permissions("planner", PLANNER_CFG, tmp_path)
    inject_role_permissions("coder", CODER_CFG, tmp_path)
    content = (tmp_path / "CLAUDE.md").read_text()
    assert content.count(BLOCK_START) == 1
    block_body = content.split(BLOCK_START)[1].split(BLOCK_END)[0]
    assert "coder" in block_body
    assert "planner" not in block_body


def test_existing_content_preserved_on_role_switch(tmp_path):
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("Read bootstrap.md before each task.\n")
    inject_role_permissions("planner", PLANNER_CFG, tmp_path)
    inject_role_permissions("coder", CODER_CFG, tmp_path)
    content = claude_md.read_text()
    assert "Read bootstrap.md before each task." in content


# --- idempotency ---

def test_idempotent_same_role(tmp_path):
    inject_role_permissions("planner", PLANNER_CFG, tmp_path)
    inject_role_permissions("planner", PLANNER_CFG, tmp_path)
    content = (tmp_path / "CLAUDE.md").read_text()
    assert content.count(BLOCK_START) == 1


# --- constraint content ---

def test_planner_no_file_write_constraint(tmp_path):
    inject_role_permissions("planner", PLANNER_CFG, tmp_path)
    content = (tmp_path / "CLAUDE.md").read_text()
    assert "Do NOT modify or delete any existing code files" in content


def test_planner_no_git_commit_constraint(tmp_path):
    inject_role_permissions("planner", PLANNER_CFG, tmp_path)
    content = (tmp_path / "CLAUDE.md").read_text()
    assert "Do NOT run git commit" in content


def test_coder_no_file_write_restriction(tmp_path):
    """Coder has file_write=True so that line must NOT appear."""
    inject_role_permissions("coder", CODER_CFG, tmp_path)
    content = (tmp_path / "CLAUDE.md").read_text()
    assert "Do NOT modify or delete any existing code files" not in content


def test_coder_git_push_restricted(tmp_path):
    inject_role_permissions("coder", CODER_CFG, tmp_path)
    content = (tmp_path / "CLAUDE.md").read_text()
    assert "Do NOT run git push" in content


def test_block_includes_role_tools(tmp_path):
    inject_role_permissions("planner", PLANNER_CFG, tmp_path)
    content = (tmp_path / "CLAUDE.md").read_text()
    assert "harness memory query" in content
    assert "harness map drill" in content


def test_coder_tools_include_mistakes_and_rules(tmp_path):
    inject_role_permissions("coder", CODER_CFG, tmp_path)
    content = (tmp_path / "CLAUDE.md").read_text()
    assert "harness mistakes" in content
    assert "harness rules check" in content
