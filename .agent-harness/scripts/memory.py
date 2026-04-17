"""Memory system — save, query, forget, access tracking."""

import sys
import re
import fnmatch
from pathlib import Path
from datetime import date, datetime

from scripts.common import (
    HARNESS_DIR, acquire_lock, release_lock, today_str,
    load_memory_index, save_memory_index, load_config,
)
from scripts.prune import prune_memory

ENTRIES_DIR = HARNESS_DIR / "memory" / "entries"
CATEGORIES = ["architecture", "pattern", "decision", "convention", "mistake"]


def _next_entry_id(entries: list) -> str:
    if not entries:
        return "mem-001"
    nums = []
    for e in entries:
        m = re.match(r"mem-(\d+)", e.get("id", ""))
        if m:
            nums.append(int(m.group(1)))
    return f"mem-{(max(nums) + 1):03d}" if nums else "mem-001"


def _score_entry(entry: dict, topic: str | None, files: list | None, categories: list | None) -> float:
    """Keyword + file relevance score. Returns 0.0 if no match."""
    score = 0.0

    if categories and entry.get("category") not in categories:
        return 0.0

    if topic:
        summary = entry.get("summary", "").lower()
        topic_lower = topic.lower()
        if topic_lower in summary:
            score += 1.0
        else:
            words = topic_lower.split()
            hits = sum(1 for w in words if w in summary)
            score += hits / max(len(words), 1) * 0.5

    if files:
        entry_files = entry.get("files", [])
        for ef in entry_files:
            for qf in files:
                if fnmatch.fnmatch(qf, ef) or ef in qf or qf in ef:
                    score += 0.8
                    break

    if topic is None and files is None:
        score = entry.get("relevance", 0.5)

    return score


def memory_query(topic: str | None, files: list | None,
                 categories: list | None = None, brief: bool = False):
    cfg = load_config()
    budgets = cfg.get("budgets", {})
    max_entries = budgets.get("memory_query_max_entries", 5)
    full_cap = budgets.get("memory_query_full_chars", 500)
    brief_cap = budgets.get("memory_query_brief_chars", 200)
    char_cap = brief_cap if brief else full_cap

    index = load_memory_index()
    entries = index.get("entries", [])

    scored = []
    for e in entries:
        s = _score_entry(e, topic, files, categories)
        if s > 0:
            scored.append((s, e))

    scored.sort(key=lambda x: (-x[0], -x[1].get("relevance", 0)))
    top = scored[:max_entries]

    if not top:
        print("No matching memory entries.")
        return

    # Bump relevance for accessed entries (write under lock)
    accessed_ids = [e["id"] for _, e in top]
    _bump_relevance(accessed_ids)

    # Print results
    for _, e in top:
        entry_id = e["id"]
        category = e.get("category", "")
        summary = e.get("summary", "")
        files_str = ", ".join(e.get("files", []))
        print(f"[{entry_id}] ({category}) {summary}")
        if files_str:
            print(f"  files: {files_str}")

        if not brief:
            entry_path = ENTRIES_DIR / f"{entry_id}.md"
            if entry_path.exists():
                content = entry_path.read_text()
                # Strip frontmatter
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    body = parts[2].strip() if len(parts) >= 3 else content
                else:
                    body = content
                if len(body) > char_cap:
                    body = body[:char_cap] + f"... [more: harness memory query {entry_id}]"
                print(f"  {body}")
        print()


def _bump_relevance(entry_ids: list):
    cfg = load_config()
    bump = cfg.get("memory", {}).get("access_bump", 0.3)
    lock = acquire_lock()
    try:
        index = load_memory_index()
        entries = index.get("entries", [])
        today = today_str()
        for e in entries:
            if e["id"] in entry_ids:
                e["relevance"] = min(1.0, e.get("relevance", 0.5) + bump)
                e["last_relevant"] = today
        save_memory_index(index)
    finally:
        release_lock(lock)


def memory_save(category: str, content: str, files: list | None = None):
    cfg = load_config()
    mem_cfg = cfg.get("memory", {})
    max_entries = mem_cfg.get("max_entries", 200)

    lock = acquire_lock()
    try:
        index = load_memory_index()
        entries = index.get("entries", [])

        # Pre-write prune if at capacity
        if len(entries) >= max_entries:
            release_lock(lock)
            prune_memory()
            lock = acquire_lock()
            index = load_memory_index()
            entries = index.get("entries", [])

        entry_id = _next_entry_id(entries)
        today = today_str()
        summary = content[:100].replace("\n", " ")

        # Write full entry file
        ENTRIES_DIR.mkdir(parents=True, exist_ok=True)
        entry_path = ENTRIES_DIR / f"{entry_id}.md"
        frontmatter = (
            f"---\nid: {entry_id}\ncategory: {category}\n"
            f"summary: \"{summary}\"\n"
            f"files: {files or []}\n"
            f"created: {today}\n---\n\n"
        )
        entry_path.write_text(frontmatter + content)

        # Append to index
        entries.append({
            "id": entry_id,
            "category": category,
            "summary": summary,
            "files": files or [],
            "created": today,
            "last_relevant": today,
            "relevance": 1.0,
        })
        index["entries"] = entries
        save_memory_index(index)

        print(f"Saved {entry_id} [{category}]: {summary[:60]}")
    finally:
        release_lock(lock)


def memory_forget(entry_id: str):
    lock = acquire_lock()
    try:
        index = load_memory_index()
        entries = index.get("entries", [])
        before = len(entries)
        index["entries"] = [e for e in entries if e["id"] != entry_id]
        save_memory_index(index)

        entry_path = ENTRIES_DIR / f"{entry_id}.md"
        if entry_path.exists():
            entry_path.unlink()

        removed = before - len(index["entries"])
        if removed:
            print(f"Removed {entry_id}")
        else:
            print(f"Entry {entry_id} not found")
    finally:
        release_lock(lock)
