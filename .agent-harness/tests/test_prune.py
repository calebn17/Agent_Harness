"""Tests for prune.py: decay rates, threshold removal, hard cap, no-op write guard."""

import time
import pytest
import yaml
from datetime import date, timedelta
from scripts.prune import prune_memory, prune_test_results


def _write_index(harness_dir, entries):
    (harness_dir / "memory" / "index.yaml").write_text(yaml.dump({"entries": entries}))


def _read_index(harness_dir):
    return yaml.safe_load((harness_dir / "memory" / "index.yaml").read_text())


def _entry(id, category="pattern", relevance=1.0, days_old=0):
    last = (date.today() - timedelta(days=days_old)).isoformat()
    return {
        "id": id, "category": category, "summary": f"entry {id}",
        "relevance": relevance, "last_relevant": last, "files": [],
    }


# --- decay rates ---

def test_decay_default_rate_causes_removal(harness_env):
    """Default decay (0.05/day) on a 3-day-old entry at relevance=0.25:
    0.25 - (0.05 * 3) = 0.10, which is exactly at the threshold.
    A 4-day-old entry at 0.25 drops to 0.05 and gets removed.
    """
    harness_dir = harness_env["harness_dir"]
    (harness_dir / "memory" / "entries" / "mem-001.md").write_text("will be removed")
    _write_index(harness_dir, [_entry("mem-001", category="pattern", relevance=0.25, days_old=4)])
    prune_memory()
    index = _read_index(harness_dir)
    # After decay: 0.25 - (0.05 * 4) = 0.05 < threshold(0.1) → removed
    assert len(index["entries"]) == 0


def test_decay_mistake_rate_is_slower(harness_env):
    """Mistake entries decay at 0.02/day vs 0.05/day for others.
    A mistake entry with relevance=0.25 after 4 days: 0.25 - (0.02 * 4) = 0.17 → survives.
    A non-mistake entry with the same starting relevance after 4 days: 0.05 → removed.
    This proves the slower rate.
    """
    harness_dir = harness_env["harness_dir"]
    _write_index(harness_dir, [
        _entry("mem-001", category="mistake", relevance=0.25, days_old=4),   # should survive
        _entry("mem-002", category="pattern", relevance=0.25, days_old=4),   # should be removed
    ])
    (harness_dir / "memory" / "entries" / "mem-001.md").write_text("mistake - keep")
    (harness_dir / "memory" / "entries" / "mem-002.md").write_text("pattern - remove")
    prune_memory()
    index = _read_index(harness_dir)
    ids = [e["id"] for e in index["entries"]]
    assert "mem-001" in ids    # mistake survived (0.17 > 0.1)
    assert "mem-002" not in ids  # non-mistake removed (0.05 < 0.1)


def test_no_decay_for_fresh_entry(harness_env):
    harness_dir = harness_env["harness_dir"]
    _write_index(harness_dir, [_entry("mem-001", relevance=0.8, days_old=0)])
    prune_memory()
    index = _read_index(harness_dir)
    assert index["entries"][0]["relevance"] == pytest.approx(0.8)


def test_relevance_floored_at_zero(harness_env):
    harness_dir = harness_env["harness_dir"]
    # 100 days of decay on a non-mistake would be -5.0; should floor at 0
    _write_index(harness_dir, [_entry("mem-001", relevance=1.0, days_old=100)])
    prune_memory()
    index = _read_index(harness_dir)
    # Entry removed since relevance dropped below threshold, OR at zero
    remaining = [e for e in index["entries"] if e["id"] == "mem-001"]
    if remaining:
        assert remaining[0]["relevance"] >= 0.0


# --- threshold removal ---

def test_below_threshold_removed_from_index(harness_env):
    harness_dir = harness_env["harness_dir"]
    _write_index(harness_dir, [
        _entry("mem-001", relevance=0.5),   # keep
        _entry("mem-002", relevance=0.05),  # remove (below 0.1 threshold)
    ])
    (harness_dir / "memory" / "entries" / "mem-001.md").write_text("keep")
    (harness_dir / "memory" / "entries" / "mem-002.md").write_text("remove")

    prune_memory()
    index = _read_index(harness_dir)
    ids = [e["id"] for e in index["entries"]]
    assert "mem-001" in ids
    assert "mem-002" not in ids


def test_below_threshold_entry_file_deleted(harness_env):
    harness_dir = harness_env["harness_dir"]
    _write_index(harness_dir, [_entry("mem-001", relevance=0.05)])
    (harness_dir / "memory" / "entries" / "mem-001.md").write_text("gone")
    prune_memory()
    assert not (harness_dir / "memory" / "entries" / "mem-001.md").exists()


# --- hard cap ---

def test_hard_cap_cuts_lowest_relevance(harness_env):
    """6 entries all above threshold, max=5 → lowest relevance cut."""
    harness_dir = harness_env["harness_dir"]
    entries = [
        _entry(f"mem-00{i}", relevance=0.5 + i * 0.05)
        for i in range(1, 7)  # 6 entries; relevances 0.55, 0.60, ..., 0.80
    ]
    _write_index(harness_dir, entries)
    prune_memory()
    index = _read_index(harness_dir)
    assert len(index["entries"]) <= 5
    ids = [e["id"] for e in index["entries"]]
    assert "mem-001" not in ids  # lowest relevance (0.55) should be cut


def test_hard_cap_keeps_highest_relevance(harness_env):
    harness_dir = harness_env["harness_dir"]
    entries = [
        _entry(f"mem-00{i}", relevance=0.5 + i * 0.05)
        for i in range(1, 7)
    ]
    _write_index(harness_dir, entries)
    prune_memory()
    index = _read_index(harness_dir)
    ids = [e["id"] for e in index["entries"]]
    assert "mem-006" in ids  # highest relevance (0.80) always kept


# --- no-op write guard (critical for skip-if-unchanged) ---

def test_index_not_written_when_nothing_changed(harness_env):
    """If all entries survive pruning, index mtime must not change.

    This is critical: an unnecessary write would update index.yaml's mtime,
    invalidating gen_bootstrap's skip-if-unchanged hash check.
    """
    harness_dir = harness_env["harness_dir"]
    _write_index(harness_dir, [_entry("mem-001", relevance=0.9, days_old=0)])

    index_path = harness_dir / "memory" / "index.yaml"
    mtime_before = index_path.stat().st_mtime

    time.sleep(0.05)  # ensure any write would be detectable
    prune_memory()

    assert index_path.stat().st_mtime == mtime_before, (
        "prune_memory() rewrote index.yaml even though no entries changed — "
        "this invalidates the bootstrap skip-if-unchanged optimization"
    )


# --- test results pruning ---

def test_test_results_pruned_to_max(harness_env):
    harness_dir = harness_env["harness_dir"]
    results_file = harness_dir / "logs" / "test-results.jsonl"
    lines = [f'{{"run": {i}}}' for i in range(10)]
    results_file.write_text("\n".join(lines) + "\n")

    prune_test_results()

    kept = results_file.read_text().strip().splitlines()
    assert len(kept) == 5  # max_results=5 per test config


def test_test_results_keeps_most_recent(harness_env):
    harness_dir = harness_env["harness_dir"]
    results_file = harness_dir / "logs" / "test-results.jsonl"
    lines = [f'{{"run": {i}}}' for i in range(10)]
    results_file.write_text("\n".join(lines) + "\n")

    prune_test_results()

    kept = results_file.read_text().strip().splitlines()
    assert kept[0] == '{"run": 5}'   # oldest kept
    assert kept[-1] == '{"run": 9}'  # most recent kept


def test_test_results_noop_when_under_limit(harness_env):
    harness_dir = harness_env["harness_dir"]
    results_file = harness_dir / "logs" / "test-results.jsonl"
    results_file.write_text('{"run": 0}\n{"run": 1}\n')
    mtime_before = results_file.stat().st_mtime

    time.sleep(0.05)
    prune_test_results()

    assert results_file.stat().st_mtime == mtime_before
