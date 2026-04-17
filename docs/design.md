# Agent Harness — Design Document

## Context & Motivation

Working with AI coding agents across projects surfaces a consistent set of problems:

1. **Context loss between sessions** — agents re-explore code they've already seen, repeat corrected mistakes, and start cold every time
2. **Manual setup overhead** — configuring each agent platform per project is tedious and inconsistent
3. **No feedback loop** — corrections don't persist; the same mistakes happen again
4. **Inconsistent quality** — without enforced conventions, agents produce code that doesn't match the project's patterns

The harness solves these by providing a **shared, token-efficient context layer** any agent can consume, with scripts handling the bookkeeping.

**Primary constraint: token and memory efficiency.** Every design decision optimizes for this first.

---

## Architecture

### Approach: Hybrid (File Bootstrap + CLI On-Demand)

The harness uses two interaction modes:

1. **File bootstrap** — a single `context/bootstrap.md` (~500 tokens / ~2000 chars) generated before each session. This is the only file an agent is guaranteed to read. Contains role-filtered context: session handoff, diff summary, project map, active mistakes, conventions, available commands.

2. **CLI on-demand** — agents call `harness <command>` to pull more context when needed. Memory queries, map drill-downs, test results, rule checks. Agents pay tokens only for what they actually need.

This avoids the two failure modes of simpler approaches:
- **File-only**: loads everything upfront, wastes tokens on irrelevant context
- **CLI-only**: requires shell access for everything, breaks agents that only read files

### Directory Structure

```
.agent-harness/
├── harness                  # CLI entrypoint (Python, argparse)
├── config.yaml              # project config: thresholds, roles, budgets
│
├── context/                 # GENERATED — agents read only
│   ├── bootstrap.md         # always-loaded context (~500 tokens)
│   ├── .bootstrap-hash      # skip-if-unchanged optimization
│   ├── session-handoff.md   # last session summary
│   └── detail/              # on-demand map files
│       └── map-*.md
│
├── memory/
│   ├── index.yaml           # thin index (id, category, summary, relevance)
│   └── entries/             # full entry files, loaded via CLI query
│
├── rules/
│   └── conventions.yaml     # project-specific rules
│
├── logs/
│   └── test-results.jsonl   # structured test history (CLI-only)
│
├── scripts/                 # all automation (Python/bash)
│   ├── gen_bootstrap.py
│   ├── sync_map.py
│   ├── parse_tests.py
│   ├── prune.py
│   └── ...
│
└── templates/               # harness init starters
    ├── ios-swift/
    ├── python/
    ├── node/
    └── nextjs/
```

### Session Lifecycle

```
harness init            → one-time: full scan, git hooks, auto-wire agent configs

git commit              → post-commit hook: sync_map.py --only <changed_dirs>
git pull/merge          → post-merge hook: same
git checkout            → post-checkout hook: staleness check, remove deleted modules

harness prep [--role X] → pre-session:
                          1. hash check → skip if unchanged
                          2. gen_bootstrap.py (role-filtered, inline confidence)
                          3. prune.py (memory + test results)

Agent session           → reads bootstrap.md, calls CLI on demand

harness post            → post-session: validate + save handoff
```

---

## Feature Design

### Bootstrap (~500 tokens, role-filtered)

Budget in characters (~2000 total, ~400 headroom):

| Section | Budget | Notes |
|---|---|---|
| Role header | 200 | Static per role |
| Session handoff | 400 | Previous session summary |
| Diff summary | 300 | Git changes since last session |
| Project map | 500 | Top-level modules, 1 line each |
| Active mistakes | 300 | Max 5 most relevant |
| Conventions | 200 | Top 5-8 rules |
| Commands | 100 | CLI reference |

`gen_bootstrap.py` enforces budgets. Overflow is truncated with a terse CLI pointer (`[more: harness map drill auth]`). Compact formatting throughout — no blank lines, minimal markdown.

**Skip-if-unchanged:** Hashes inputs (HEAD SHA, file mtimes). Skips regeneration if unchanged. Common case when re-entering a session.

### Memory System

Two-tier to keep injection cost minimal:

**Index** (`memory/index.yaml`) — always available to CLI, not injected directly:
```yaml
- id: mem-001
  category: mistake
  summary: "Don't use assertEqual for async — use await expect"
  files: ["tests/**"]
  relevance: 0.8
  last_relevant: 2026-04-16
```

**Entries** (`memory/entries/mem-*.md`) — full content, loaded by CLI query only.

**Relevance decay** prevents stale memories from persisting:
- Default decay: -0.05/day when not accessed
- Mistake decay: -0.02/day (slower — corrections stay longer)
- Access bump: +0.3 when queried (capped at 1.0, not reset — prevents immortal entries)
- Prune threshold: 0.1 relevance

**Write locking** for concurrent agents: `fcntl.flock(LOCK_EX)` on `.agent-harness/.lock`. Covers read-index → write-entry → update-index atomically. Blocks (doesn't fail). Applied to memory writes and test-results.jsonl.

**Pre-write prune:** `harness memory save` checks count >= max before writing. If at capacity, prunes inline before saving. Ensures hard cap is enforced at write time, not just during prep.

### Codebase Map

Generated incrementally, never during `harness prep`:

- `harness init` → full scan (one-time, via `sync_map.py`)
- Post-commit hook → `sync_map.py --only <changed_dirs>` (git diff-tree identifies what changed)
- Post-merge hook → same
- Post-checkout hook → staleness check, removes entries for deleted modules

Top-level summary (`map-root.md`) is inlined into bootstrap (~500 chars). Per-module detail files (~800-1600 chars each) are served on demand via `harness map drill`.

`sync_map.py` uses directory walking with language detection (file extension counting). Respects `.gitignore`-style patterns. For deleted modules, checks if the path still exists and removes the stale detail file.

### Confidence Scoring (Inlined)

Not a separate system. ~10 lines in `gen_bootstrap.py`:

```python
score = base_familiarity * recency_multiplier * (1 - mistake_penalty)
base_familiarity = min(sessions_touched / 10, 1.0)       # git log count
recency_multiplier = max(1.0 - (days_since * 0.03), 0.2) # 3%/day decay
mistake_penalty = min(mistake_count * 0.1, 0.5)           # from memory index
```

Used to prioritize what to surface in the bootstrap (low-confidence areas get more detail). No stored artifact — computed fresh from git log + memory index.

### Role System

Roles live in `config.yaml` under `roles:`. Each role defines:
- `models` — which LLMs fill this role
- `permissions` — file_write, git_commit, etc.
- `bootstrap.sections` — which bootstrap sections to include
- `bootstrap.mistake_categories` — which mistake types to surface
- `tools` — which CLI commands are listed as available

**Role assignments:**
- **Planner** (Claude Opus): read-heavy, can create plan docs, no code writes
- **Coder** (Sonnet / Cursor Composer 2): full write access, can commit
- **Reviewer** (Codex): read + suggest fixes, expanded conventions view

Permissions are translated to each platform's native format during `harness prep` (CLAUDE.md `permissions`, `.cursorrules` instructions, AGENTS.md constraints).

### Concurrent Agents via Worktrees

Each agent works in its own git worktree on a separate branch. `.agent-harness/` is shared. `harness prep --worktree <path>` writes bootstrap into the worktree, not the shared directory. Memory, map, and rules are shared — all agents benefit from each other's memories.

Write safety:
- Memory writes: flock on `.lock`
- Test results: flock on `.lock`
- Map updates: per-branch via post-commit hook (no contention)
- Bootstrap: written to worktree-local path (no contention)

### Test Results

Stored in `logs/test-results.jsonl`. Written by `parse_tests.py`, which auto-detects pytest/jest/xcode output. Two entry points:
- `harness test` — runs configured test command, pipes through parser
- `<cmd> 2>&1 | harness parse-test-output` — for agents using their own test invocation

Pruned to last 20 runs (hard truncation, no compression). Flock-protected writes.

### Conventions Engine

Rules in `rules/conventions.yaml`. Two enforcement layers:
1. **Passive** — top 5-8 rules summarized in bootstrap. All agents read them.
2. **Active** — `harness rules check [--staged] [--files X]` validates via regex pattern matching.

Pattern checks are lightweight (not a full linter). Covers: banned function calls, import style, naming conventions. Existing tools (eslint, ruff, swiftlint) handle the rest.

Template-specific knowledge lives here as initial rules — not in memory. Generic project-type conventions (e.g., "use app router") belong in conventions, not in memory entries.

### harness init

Sets up harness from a template:
1. Create directory structure
2. Copy template `config.yaml` and `conventions.yaml`
3. Full codebase map scan
4. Install git hooks (post-commit, post-merge, post-checkout)
5. Generate initial bootstrap
6. Auto-wire agent configs (append bootstrap reference to CLAUDE.md, .cursorrules, AGENTS.md — idempotent)

Templates: `ios-swift`, `python`, `node`, `nextjs`. Each provides conventions tuned for that stack.

---

## What Was Deliberately Left Out

**Activity log** — originally designed as a structured log of agent actions. Eliminated because its only consumers (confidence scoring, analytics) could be served by git log and the memory index directly. Avoids an append-only file that grows every session and needs complex pruning.

**Standalone confidence file** — eliminated as a stored artifact. Scoring is 10 lines inlined in `gen_bootstrap.py`. Same value, zero overhead.

**Separate roles directory** — collapsed into `config.yaml`. Three YAML files for what's essentially a lookup table added complexity without value.

**Memory seeds in templates** — generic project-type knowledge goes in `conventions.yaml`, not in memory entries. Memory is for project-specific learned knowledge, not generic best practices.

**Feedback loop as infrastructure** — the plan→develop→test workflow is documented as guidance, not enforced by the harness. The primitives (bootstrap, memory, test results, rules check) enable it organically.

**Vector/embedding search** — adds a dependency (embedding model, vector DB) for marginal gain. Keyword + recency scoring is sufficient at this scale.

---

## Token Cost Summary

| Component | Per-session cost | Growth risk |
|---|---|---|
| Bootstrap | ~500 tokens (fixed) | None (capped) |
| Memory query (full, 5 entries) | ~625 tokens | None (capped) |
| Map drill | ~400 tokens | Low (project-size bound) |
| Test results (last 5) | ~300 tokens | None (capped at 20 runs) |
| Rules check | ~200 tokens | Low (rules rarely change) |

Worst case (bootstrap + all CLI commands) ≈ 2000 tokens per session. Typical sessions use 700-1000 tokens of harness context.
