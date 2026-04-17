"""Tests for the memory system: save, query, forget, access tracking, pre-write prune."""

import pytest
import yaml
from scripts.memory import memory_save, memory_query, memory_forget


def _read_index(harness_dir):
    return yaml.safe_load((harness_dir / "memory" / "index.yaml").read_text())


def _set_relevance(harness_dir, entry_id, value):
    index = _read_index(harness_dir)
    for e in index["entries"]:
        if e["id"] == entry_id:
            e["relevance"] = value
    (harness_dir / "memory" / "index.yaml").write_text(yaml.dump(index))


# --- save / query ---

def test_save_creates_index_entry(harness_env):
    harness_dir = harness_env["harness_dir"]
    memory_save("pattern", "Always use async/await in API handlers")
    index = _read_index(harness_dir)
    assert len(index["entries"]) == 1
    assert index["entries"][0]["id"] == "mem-001"
    assert index["entries"][0]["category"] == "pattern"


def test_save_creates_entry_file(harness_env):
    harness_dir = harness_env["harness_dir"]
    memory_save("mistake", "Never call os.system in production")
    assert (harness_dir / "memory" / "entries" / "mem-001.md").exists()


def test_sequential_ids(harness_env):
    memory_save("pattern", "First")
    memory_save("mistake", "Second")
    harness_dir = harness_env["harness_dir"]
    ids = [e["id"] for e in _read_index(harness_dir)["entries"]]
    assert ids == ["mem-001", "mem-002"]


def test_query_by_topic_finds_match(harness_env, capsys):
    memory_save("pattern", "Always use async/await in API handlers")
    memory_query(topic="async API", files=None)
    assert "mem-001" in capsys.readouterr().out


def test_query_no_match_prints_message(harness_env, capsys):
    memory_save("pattern", "Always use async/await")
    memory_query(topic="zymurgical obscure topic", files=None)
    assert "No matching" in capsys.readouterr().out


def test_query_by_file_glob(harness_env, capsys):
    memory_save("mistake", "Never use raw SQL in auth handlers", files=["src/auth/*"])
    memory_query(topic=None, files=["src/auth/login.py"])
    assert "mem-001" in capsys.readouterr().out


def test_query_by_category_filter(harness_env, capsys):
    memory_save("pattern", "Use dependency injection")
    memory_save("mistake", "Don't use globals")
    capsys.readouterr()  # flush save() output before checking query output
    memory_query(topic=None, files=None, categories=["mistake"])
    out = capsys.readouterr().out
    assert "mem-002" in out
    assert "mem-001" not in out


# --- relevance bump on access ---

def test_query_bumps_relevance(harness_env):
    harness_dir = harness_env["harness_dir"]
    memory_save("pattern", "Use dependency injection")
    _set_relevance(harness_dir, "mem-001", 0.5)

    memory_query(topic="dependency injection", files=None)

    index = _read_index(harness_dir)
    assert index["entries"][0]["relevance"] == pytest.approx(0.8)  # 0.5 + 0.3


def test_relevance_bump_capped_at_1(harness_env):
    harness_dir = harness_env["harness_dir"]
    memory_save("pattern", "Use dependency injection")
    _set_relevance(harness_dir, "mem-001", 0.9)

    memory_query(topic="dependency injection", files=None)

    index = _read_index(harness_dir)
    assert index["entries"][0]["relevance"] == pytest.approx(1.0)  # capped, not 1.2


# --- forget ---

def test_forget_removes_from_index(harness_env):
    harness_dir = harness_env["harness_dir"]
    memory_save("mistake", "Don't use requests.get without timeout")
    memory_forget("mem-001")
    assert len(_read_index(harness_dir)["entries"]) == 0


def test_forget_deletes_entry_file(harness_env):
    harness_dir = harness_env["harness_dir"]
    memory_save("mistake", "Don't use requests.get without timeout")
    memory_forget("mem-001")
    assert not (harness_dir / "memory" / "entries" / "mem-001.md").exists()


def test_forget_nonexistent_prints_not_found(harness_env, capsys):
    memory_forget("mem-999")
    assert "not found" in capsys.readouterr().out.lower()


# --- pre-write prune ---

def test_prewrite_prune_triggers_at_max(harness_env):
    """Saving when count == max_entries triggers prune; final count stays <= max."""
    harness_dir = harness_env["harness_dir"]
    # Fill to max (5 per test config)
    for i in range(5):
        memory_save("pattern", f"Pattern number {i}")

    # Drop the oldest entry below prune threshold so prune has something to cut
    index = _read_index(harness_dir)
    index["entries"][0]["relevance"] = 0.05
    (harness_dir / "memory" / "index.yaml").write_text(yaml.dump(index))

    # Saving a 6th entry must trigger prune before writing
    memory_save("pattern", "Sixth entry — triggers pre-write prune")

    assert len(_read_index(harness_dir)["entries"]) <= 5


def test_new_entry_saved_after_prune(harness_env):
    """After pre-write prune the new entry still lands in the index."""
    harness_dir = harness_env["harness_dir"]
    for i in range(5):
        memory_save("pattern", f"Pattern {i}")

    index = _read_index(harness_dir)
    index["entries"][0]["relevance"] = 0.05
    (harness_dir / "memory" / "index.yaml").write_text(yaml.dump(index))

    memory_save("pattern", "The important new pattern")

    summaries = [e["summary"] for e in _read_index(harness_dir)["entries"]]
    assert any("important new pattern" in s for s in summaries)
