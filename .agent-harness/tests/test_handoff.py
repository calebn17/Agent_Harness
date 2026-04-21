"""Tests for handoff_cmd.py: generate handoff doc from latest git commit."""

from unittest.mock import patch
import scripts.handoff_cmd as hc


def test_handoff_file_created(tmp_path, monkeypatch):
    handoff_dir = tmp_path / "handoff"
    monkeypatch.setattr(hc, "HANDOFF_DIR", handoff_dir)
    monkeypatch.setattr(hc, "HANDOFF_FILE", handoff_dir / "handoff.md")

    with patch("scripts.handoff_cmd.subprocess.check_output") as mock_out:
        mock_out.side_effect = ["fix: resolve auth bug\n", "src/auth.py\n", "src/auth.py | 5 ++---\n"]
        hc.generate_handoff()

    assert hc.HANDOFF_FILE.exists()


def test_handoff_contains_commit_message(tmp_path, monkeypatch):
    handoff_dir = tmp_path / "handoff"
    monkeypatch.setattr(hc, "HANDOFF_DIR", handoff_dir)
    monkeypatch.setattr(hc, "HANDOFF_FILE", handoff_dir / "handoff.md")

    with patch("scripts.handoff_cmd.subprocess.check_output") as mock_out:
        mock_out.side_effect = ["fix: resolve auth bug\n", "src/auth.py\n", "src/auth.py | 5 ++---\n"]
        hc.generate_handoff()

    content = hc.HANDOFF_FILE.read_text()
    assert "fix: resolve auth bug" in content


def test_handoff_contains_changed_files(tmp_path, monkeypatch):
    handoff_dir = tmp_path / "handoff"
    monkeypatch.setattr(hc, "HANDOFF_DIR", handoff_dir)
    monkeypatch.setattr(hc, "HANDOFF_FILE", handoff_dir / "handoff.md")

    with patch("scripts.handoff_cmd.subprocess.check_output") as mock_out:
        mock_out.side_effect = ["fix: resolve auth bug\n", "src/auth.py\nsrc/models.py\n", "2 files changed\n"]
        hc.generate_handoff()

    content = hc.HANDOFF_FILE.read_text()
    assert "src/auth.py" in content
    assert "src/models.py" in content


def test_handoff_creates_parent_dir(tmp_path, monkeypatch):
    handoff_dir = tmp_path / "does_not_exist" / "handoff"
    monkeypatch.setattr(hc, "HANDOFF_DIR", handoff_dir)
    monkeypatch.setattr(hc, "HANDOFF_FILE", handoff_dir / "handoff.md")

    with patch("scripts.handoff_cmd.subprocess.check_output") as mock_out:
        mock_out.side_effect = ["msg\n", "file.py\n", "stat\n"]
        hc.generate_handoff()

    assert hc.HANDOFF_FILE.exists()
