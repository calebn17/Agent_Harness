"""Tests for handoff_cmd.py: generate handoff doc from latest git commit."""

from unittest.mock import patch
import scripts.handoff_cmd as hc


def test_handoff_file_created(harness_env, monkeypatch):
    handoff_dir = harness_env["harness_dir"] / "handoff"
    monkeypatch.setattr(hc, "HARNESS_DIR", harness_env["harness_dir"])
    monkeypatch.setattr(hc, "HANDOFF_DIR", handoff_dir)
    monkeypatch.setattr(hc, "HANDOFF_FILE", handoff_dir / "handoff.md")

    with patch("scripts.handoff_cmd.subprocess.check_output") as mock_out:
        mock_out.side_effect = ["fix: resolve auth bug\n", "src/auth.py\n", "src/auth.py | 5 ++---\n"]
        hc.generate_handoff()

    assert (handoff_dir / "handoff.md").exists()


def test_handoff_contains_commit_message(harness_env, monkeypatch):
    handoff_dir = harness_env["harness_dir"] / "handoff"
    monkeypatch.setattr(hc, "HARNESS_DIR", harness_env["harness_dir"])
    monkeypatch.setattr(hc, "HANDOFF_DIR", handoff_dir)
    monkeypatch.setattr(hc, "HANDOFF_FILE", handoff_dir / "handoff.md")

    with patch("scripts.handoff_cmd.subprocess.check_output") as mock_out:
        mock_out.side_effect = ["fix: resolve auth bug\n", "src/auth.py\n", "src/auth.py | 5 ++---\n"]
        hc.generate_handoff()

    content = (handoff_dir / "handoff.md").read_text()
    assert "fix: resolve auth bug" in content


def test_handoff_contains_changed_files(harness_env, monkeypatch):
    handoff_dir = harness_env["harness_dir"] / "handoff"
    monkeypatch.setattr(hc, "HARNESS_DIR", harness_env["harness_dir"])
    monkeypatch.setattr(hc, "HANDOFF_DIR", handoff_dir)
    monkeypatch.setattr(hc, "HANDOFF_FILE", handoff_dir / "handoff.md")

    with patch("scripts.handoff_cmd.subprocess.check_output") as mock_out:
        mock_out.side_effect = ["fix: resolve auth bug\n", "src/auth.py\nsrc/models.py\n", "2 files changed\n"]
        hc.generate_handoff()

    content = (handoff_dir / "handoff.md").read_text()
    assert "src/auth.py" in content
    assert "src/models.py" in content


def test_handoff_creates_parent_dir(harness_env, monkeypatch):
    handoff_dir = harness_env["harness_dir"] / "does_not_exist" / "handoff"
    monkeypatch.setattr(hc, "HARNESS_DIR", harness_env["harness_dir"])
    monkeypatch.setattr(hc, "HANDOFF_DIR", handoff_dir)
    monkeypatch.setattr(hc, "HANDOFF_FILE", handoff_dir / "handoff.md")

    with patch("scripts.handoff_cmd.subprocess.check_output") as mock_out:
        mock_out.side_effect = ["msg\n", "file.py\n", "stat\n"]
        hc.generate_handoff()

    assert (handoff_dir / "handoff.md").exists()


def test_handoff_contains_diff_stat(harness_env, monkeypatch):
    handoff_dir = harness_env["harness_dir"] / "handoff"
    monkeypatch.setattr(hc, "HARNESS_DIR", harness_env["harness_dir"])
    monkeypatch.setattr(hc, "HANDOFF_DIR", handoff_dir)
    monkeypatch.setattr(hc, "HANDOFF_FILE", handoff_dir / "handoff.md")

    with patch("scripts.handoff_cmd.subprocess.check_output") as mock_out:
        mock_out.side_effect = ["msg\n", "file.py\n", "file.py | 3 +++\n"]
        hc.generate_handoff()

    content = (handoff_dir / "handoff.md").read_text()
    assert "## Diff Summary" in content
    assert "file.py | 3 +++" in content
