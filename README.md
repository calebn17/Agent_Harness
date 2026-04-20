# Agent Harness

A token-efficient, persistent context layer for AI coding agents. Lives in any project as a git submodule. Gives Claude Code, Cursor (Composer 2), and Codex a shared memory, codebase map, and convention rules — so every session starts informed, not cold.

---

## The Problem

AI agents forget everything between sessions. They re-explore code they've already seen, repeat corrected mistakes, and ignore project-specific rules. Each session wastes tokens rebuilding context that should already be known.

## The Solution

A lightweight harness that:
- Maintains a **persistent memory** of architecture decisions, patterns, and corrections
- Generates a **codebase map** so agents know where things are without exploring
- Injects a **~500 token bootstrap** at session start — only what each role needs
- Automates bookkeeping via scripts so agents spend tokens on actual work

---

## Installation

```bash
# Prerequisite: Python 3.9+, pyyaml
pip3 install pyyaml

# Add as git submodule to your project
git submodule add <this-repo-url> .agent-harness

# Initialize for your project type
.agent-harness/harness init --type nextjs   # or python, ios-swift, node
```

`harness init` will:
- Generate an initial codebase map
- Install git hooks for incremental map updates
- Append bootstrap references to CLAUDE.md, .cursorrules, and AGENTS.md

---

## Usage

### Before each session

```bash
.agent-harness/harness prep --role coder      # Sonnet / Cursor Composer 2
.agent-harness/harness prep --role planner    # Claude Opus
.agent-harness/harness prep --role reviewer   # Codex
```

Generates `context/bootstrap.md` — the only file your agent needs to read. Fast (<1s), skips if nothing changed.

### During a session

Agents call these on demand:

```bash
harness memory query "authentication"         # retrieve relevant memories
harness memory query --files "src/auth/*.ts"  # file-scoped query
harness memory save --category pattern "..."  # save something learned
harness mistakes for "src/auth/login.ts"      # check known pitfalls for a file
harness map drill "src/auth"                  # detailed module map
harness rules check --staged                  # validate before commit
harness test                                  # run tests + capture results
harness test-results "src/auth"               # last N failures for a path
```

### After a session

Write a handoff summary to `context/session-handoff.md`. Run:

```bash
harness post    # validates handoff, persists memories
```

---

## Roles

| Role | Model | What they get |
|---|---|---|
| **planner** | Claude Opus | Project map, conventions, architecture context |
| **coder** | Sonnet / Composer 2 | Full context: map, mistakes, diff, conventions |
| **reviewer** | Codex | Diff, mistakes, full conventions, test results |

Each role gets a filtered bootstrap. Planner doesn't see test failures. Reviewer gets the full convention list. Coder gets active mistakes for current files.

---

## Concurrent Agents (Worktrees)

Works with git worktrees for parallel agent sessions:

```bash
# Main branch — Opus planning
harness prep --role planner

# Feature branch — Sonnet coding
git worktree add ../my-feature -b feature/my-feature
harness prep --role coder --worktree ../my-feature

# Review branch — Codex reviewing
git worktree add ../review feature/my-feature
harness prep --role reviewer --worktree ../review
```

Each worktree gets its own `bootstrap.md`. Memory and map are shared. Write contention is handled by file locking.

---

## Memory System

Two-tier: a thin index always available, full entries loaded on demand.

**Categories:** `architecture` | `pattern` | `decision` | `convention` | `mistake`

```bash
harness memory save --category mistake "Don't use assertEqual for async — use await expect"
harness memory save --category architecture "Auth uses middleware chain, not decorators"
harness memory query "async testing" --brief
```

Memories decay over time (-0.05 relevance/day). Mistakes decay slower (-0.02/day). Accessed entries get a +0.3 bump. Entries below 0.1 relevance are pruned automatically.

---

## Token Budget

| Component | Characters | ~Tokens |
|---|---|---|
| Bootstrap (all sections) | ~2000 chars | ~500 tokens |
| Memory query (full, 5 entries) | ~2500 chars | ~625 tokens |
| Map drill (one module) | ~1600 chars | ~400 tokens |

Agents spend tokens on reasoning, not context rebuilding.

---

## Project Structure

```
.agent-harness/
├── harness              # CLI (run this)
├── config.yaml          # roles, budgets, test command
├── context/
│   ├── bootstrap.md     # agents read this
│   └── detail/          # on-demand map files
├── memory/              # persistent agent memory
├── rules/               # project conventions
├── logs/                # test results (CLI-only)
├── scripts/             # all automation
└── templates/           # harness init starters
```

---

## Running the Tests

The harness ships with a pytest suite covering memory, pruning, permissions injection, bootstrap generation, and CLI integration.

```bash
# Install test dependency (pyyaml is already required)
pip3 install pytest

# Run from inside .agent-harness/
cd .agent-harness
python3 -m pytest tests/ -v
```

Expected output: 60 tests, all passing, ~2s.

Each test gets an isolated temp directory — no real harness data is touched.

---

## Configuration

Edit `.agent-harness/config.yaml`:

- `project.type` — template type
- `budgets.*` — token/char limits per command
- `memory.*` — max entries, decay rates, prune threshold
- `tests.test_command` — your test runner command
- `roles.*` — permissions and context per role
