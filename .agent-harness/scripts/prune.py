"""Prune memory and test results to stay within configured thresholds."""

from datetime import date, datetime
from pathlib import Path

from scripts.common import (
    HARNESS_DIR, acquire_lock, release_lock, today_str,
    load_memory_index, save_memory_index, load_config,
)

ENTRIES_DIR = HARNESS_DIR / "memory" / "entries"
TEST_RESULTS = HARNESS_DIR / "logs" / "test-results.jsonl"


def _apply_decay(entry: dict, today: date, decay_default: float, decay_mistake: float) -> dict:
    """Decay relevance based on days since last_relevant."""
    last_str = entry.get("last_relevant") or entry.get("created") or today_str()
    try:
        last = date.fromisoformat(str(last_str))
    except ValueError:
        last = today
    days = max((today - last).days, 0)
    rate = decay_mistake if entry.get("category") == "mistake" else decay_default
    decayed = entry.get("relevance", 1.0) - (rate * days)
    entry["relevance"] = max(0.0, decayed)
    return entry


def prune_memory():
    cfg = load_config()
    mem_cfg = cfg.get("memory", {})
    max_entries = mem_cfg.get("max_entries", 200)
    decay_default = mem_cfg.get("decay_default", 0.05)
    decay_mistake = mem_cfg.get("decay_mistake", 0.02)
    prune_threshold = mem_cfg.get("prune_threshold", 0.1)

    today = date.today()

    lock = acquire_lock()
    try:
        index = load_memory_index()
        entries = index.get("entries", [])

        # Apply decay
        entries = [_apply_decay(e, today, decay_default, decay_mistake) for e in entries]

        # Remove below threshold
        to_remove = [e["id"] for e in entries if e["relevance"] < prune_threshold]
        entries = [e for e in entries if e["relevance"] >= prune_threshold]

        # Hard cap: if still over max, cut lowest relevance
        if len(entries) > max_entries:
            entries.sort(key=lambda e: e.get("relevance", 0), reverse=True)
            to_remove += [e["id"] for e in entries[max_entries:]]
            entries = entries[:max_entries]

        # Delete entry files
        for entry_id in to_remove:
            entry_path = ENTRIES_DIR / f"{entry_id}.md"
            if entry_path.exists():
                entry_path.unlink()

        if to_remove:
            index["entries"] = entries
            save_memory_index(index)
            print(f"Pruned {len(to_remove)} memory entries.")
    finally:
        release_lock(lock)


def prune_test_results():
    cfg = load_config()
    max_results = cfg.get("tests", {}).get("max_results", 20)

    if not TEST_RESULTS.exists():
        return

    lock = acquire_lock()
    try:
        lines = TEST_RESULTS.read_text().splitlines()
        if len(lines) > max_results:
            kept = lines[-max_results:]
            TEST_RESULTS.write_text("\n".join(kept) + "\n")
    finally:
        release_lock(lock)


def prune_all():
    prune_memory()
    prune_test_results()
