# Agent Harness Refactor — Design Spec
**Date:** 2026-04-20  
**Status:** Approved

---

## Context

The Agent Harness was built to give AI agents persistent context (memory, codebase map, mistakes log) across sessions. The original design included manual CLI commands (`harness prep --role X`, `harness post`) and explicit handoff templates that agents had to be told to write. In practice this created friction: users had to remember script names, instruct agents to write handoffs, and manage artifact cleanup manually.

The goal of this refactor is to replace manual CLI ceremony with skills — markdown instruction files that agents invoke autonomously. Agents should self-guide through their workflow without user intervention beyond initial project setup.

---

## Core Principle

**Tool identity = Role identity.** No explicit `--role` flag needed. Each agent tool is hardwired to a role:

| Tool | Role | Primary Artifact |
|---|---|---|
| Claude Code | Planner | Plan docs in `docs/plans/` (persisted) |
| Cursor | Coder | Memory entries (handoff doc is transient) |
| Codex | Reviewer | Review doc (transient, deleted after coder reads) |

The `harness` CLI becomes internal plumbing. Agents interact exclusively through skills.

---

## Skills Architecture

Skills are markdown files in `.agent-harness/skills/<role>/`. Each file contains instructions the agent reads and follows — including which `harness` CLI commands to run under the hood.

### Planner (Claude Code)

| Skill | Trigger | Description |
|---|---|---|
| `planner-start.md` | Session start (auto via CLAUDE.md) | Runs `harness prep --role planner`, reads bootstrap, lists plan docs in `docs/plans/` |
| `create-plan.md` | Agent-invoked when creating a plan | Scaffolds a new plan doc in `docs/plans/` |

### Coder (Cursor)

| Skill | Trigger | Description |
|---|---|---|
| `coder-start.md` | Session start (auto via .cursorrules) | Runs `harness prep --role coder`, reads bootstrap, checks for pending review docs and invokes `pick-up-review` if found |
| `pick-up-review.md` | Agent-invoked when review doc found | Read review doc → apply fixes → delete review doc |
| `save-mistake.md` | Agent-invoked autonomously during work | Saves a mistake/lesson to memory via `harness memory save` |
| `query-memory.md` | Agent-invoked when context needed | Wraps `harness memory query "<topic>"` |
| `drill-map.md` | Agent-invoked when exploring a module | Wraps `harness map drill "<module>"` |

### Reviewer (Codex)

| Skill | Trigger | Description |
|---|---|---|
| `reviewer-start.md` | Session start (auto via AGENTS.md) | Runs `harness prep --role reviewer`, reads bootstrap, reads git diff |
| `leave-review.md` | Agent-invoked when review is complete | Writes structured review doc to `.agent-harness/reviews/review-<timestamp>.md` |

---

## Artifacts & Cleanup

### Persisted (committed to git)
- `docs/plans/` — plan docs created by planner
- `.agent-harness/memory/` — memory entries and index
- `.agent-harness/context/` — bootstrap and map files

### Transient (gitignored, auto-deleted)
- `.agent-harness/reviews/review-<timestamp>.md` — written by reviewer via `leave-review`, deleted by coder after `pick-up-review` finishes applying fixes
- `.agent-harness/handoff/handoff.md` — written by post-commit hook after every commit (agent or human), ingested into memory by `coder-start`, then deleted

### Cleanup Responsibilities
- `pick-up-review`: read → apply fixes → delete review doc
- `coder-start`: if handoff doc exists → ingest to memory → delete doc
- `.gitignore`: add `.agent-harness/reviews/` and `.agent-harness/handoff/`

---

## Automated Handoff via Post-Commit Hook

The post-commit hook fires on every commit (agent or human). It writes `.agent-harness/handoff/handoff.md` summarizing what changed (git diff summary + relevant context for the next session). This replaces the manual `harness post` ceremony.

**Why fire on human commits too:** A handoff after a human commit is useful context for the next coder session. Auto-cleanup via `coder-start` means it never appears in git.

---

## Skill Wiring via Config Injection

The existing `permissions.py` tag-based injection is extended to also inject a skills block into each agent config file. `harness init` handles all injections — no manual wiring after setup.

**CLAUDE.md (Planner):**
```
<!-- agent-harness:skills:start -->
At the start of every session, read and follow .agent-harness/skills/planner/planner-start.md.
Additional skills available when needed:
- Create a plan: .agent-harness/skills/planner/create-plan.md
<!-- agent-harness:skills:end -->
```

**`.cursorrules` (Coder):**
```
<!-- agent-harness:skills:start -->
At the start of every session, read and follow .agent-harness/skills/coder/coder-start.md.
Additional skills available when needed:
- Pick up a code review: .agent-harness/skills/coder/pick-up-review.md
- Save a mistake: .agent-harness/skills/coder/save-mistake.md
- Query memory: .agent-harness/skills/coder/query-memory.md
- Drill into a module map: .agent-harness/skills/coder/drill-map.md
<!-- agent-harness:skills:end -->
```

**`AGENTS.md` (Reviewer):**
```
<!-- agent-harness:skills:start -->
At the start of every session, read and follow .agent-harness/skills/reviewer/reviewer-start.md.
When review is complete, invoke: .agent-harness/skills/reviewer/leave-review.md
<!-- agent-harness:skills:end -->
```

---

## Directory Structure

```
.agent-harness/
  skills/
    planner/
      planner-start.md
      create-plan.md
    coder/
      coder-start.md
      pick-up-review.md
      save-mistake.md
      query-memory.md
      drill-map.md
    reviewer/
      reviewer-start.md
      leave-review.md
  reviews/         ← gitignored, transient review docs
  handoff/         ← gitignored, transient handoff docs
  memory/          ← persisted
  context/         ← persisted
  scripts/         ← harness CLI internals (unchanged)
docs/
  plans/           ← persisted plan docs
```

---

## What Changes vs. Current Implementation

| Current | Refactored |
|---|---|
| `harness prep --role X` run manually | `planner-start` / `coder-start` / `reviewer-start` skill handles it |
| `harness post` run manually to write handoff | Post-commit hook auto-generates handoff doc |
| Agent must be told to write handoff | Coder-start ingests and deletes handoff automatically |
| No review workflow | `leave-review` → `pick-up-review` with auto-cleanup |
| CLAUDE.md / .cursorrules have role block only | Role block + skills block both injected by `harness init` |
| Skills don't exist | Skills directory added per role |

## What Stays the Same

- All existing `harness` CLI commands and scripts (unchanged)
- Memory decay, index, two-tier storage
- Codebase map generation and git hook incremental updates
- Bootstrap generation and token budgets
- Role definitions in `config.yaml`
- Test integration

---

## Verification

1. Run `harness init` on a test project → confirm CLAUDE.md, .cursorrules, AGENTS.md each have both a role block and a skills block injected
2. Start a Claude Code session → confirm `planner-start.md` is read and bootstrap is loaded without manual `harness prep`
3. Make a commit → confirm `.agent-harness/handoff/handoff.md` is created and is gitignored
4. Start a new coder session → confirm handoff is ingested into memory and the doc is deleted
5. Run `reviewer-start` → confirm `leave-review` creates a review doc in `.agent-harness/reviews/` and it is gitignored
6. Run `pick-up-review` → confirm review doc is deleted after fixes are applied
7. Confirm `docs/plans/` files are committed; confirm `reviews/` and `handoff/` are never committed
