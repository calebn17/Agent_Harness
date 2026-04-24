# Agent Harness Skills Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace manual CLI ceremony with skills — markdown instruction files agents invoke autonomously — so the planner/coder/reviewer workflow runs without user intervention.

**Architecture:** Each agent tool maps to a fixed role (Claude Code → planner, Cursor → coder, Codex → reviewer). Skills live in `.agent-harness/skills/<role>/` and are referenced by agent config files (CLAUDE.md, .cursorrules, AGENTS.md) via an injected skills block. A new post-commit hook generates a handoff doc automatically; `coder-start` ingests and deletes it. Review docs and handoff docs are gitignored and cleaned up after use.

**Tech Stack:** Python 3.9+, pytest, PyYAML, bash (git hooks), Markdown (skill files)

---

## File Map

**Create:**
- `.agent-harness/scripts/handoff_cmd.py` — generates handoff.md from latest git commit
- `.agent-harness/skills/planner/planner-start.md` — planner session start instructions
- `.agent-harness/skills/planner/create-plan.md` — plan scaffolding instructions
- `.agent-harness/skills/coder/coder-start.md` — coder session start instructions
- `.agent-harness/skills/coder/pick-up-review.md` — read, fix, delete review doc
- `.agent-harness/skills/coder/save-mistake.md` — save mistake to memory
- `.agent-harness/skills/coder/query-memory.md` — query memory for context
- `.agent-harness/skills/coder/drill-map.md` — drill into module map
- `.agent-harness/skills/reviewer/reviewer-start.md` — reviewer session start instructions
- `.agent-harness/skills/reviewer/leave-review.md` — write review doc instructions
- `.agent-harness/tests/test_handoff.py` — tests for handoff_cmd.py

**Modify:**
- `.gitignore` — add `.agent-harness/reviews/` and `.agent-harness/handoff/`
- `.agent-harness/scripts/permissions.py` — add skills block injection (new constants + 2 functions)
- `.agent-harness/scripts/init_cmd.py` — create reviews/ and handoff/ dirs, inject skills blocks, extend POST_COMMIT_HOOK
- `.agent-harness/tests/test_permissions.py` — add skills injection tests
- `.agent-harness/scripts/post_session.py` — add deprecation notice

---

### Task 1: Update .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add transient directory entries**

Open `.gitignore` and append after the existing `.agent-harness/` entries (after line 10, before the Python section):

```
.agent-harness/reviews/
.agent-harness/handoff/
```

Final `.gitignore` section should look like:
```
# Harness generated files (project-specific, not versioned in the submodule)
.agent-harness/context/bootstrap.md
.agent-harness/context/.bootstrap-hash
.agent-harness/context/session-handoff.md
.agent-harness/context/detail/
.agent-harness/memory/entries/
.agent-harness/memory/index.yaml
.agent-harness/logs/
.agent-harness/scores/
.agent-harness/.lock
.agent-harness/reviews/
.agent-harness/handoff/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore transient reviews/ and handoff/ directories"
```

---

### Task 2: Write handoff generation script

**Files:**
- Create: `.agent-harness/tests/test_handoff.py`
- Create: `.agent-harness/scripts/handoff_cmd.py`

- [ ] **Step 1: Write the failing test**

Create `.agent-harness/tests/test_handoff.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "/Users/calebngai/Desktop/Agentic-Engineering-Projects/Agent Harness/.agent-harness"
python3 -m pytest tests/test_handoff.py -v
```

Expected: `ModuleNotFoundError: No module named 'scripts.handoff_cmd'`

- [ ] **Step 3: Write the implementation**

Create `.agent-harness/scripts/handoff_cmd.py`:

```python
"""Generate a session handoff doc from the latest git commit.

Called automatically by the post-commit hook after every commit.
The coder-start skill reads, ingests, and deletes this file.
"""

import subprocess
from pathlib import Path

from scripts.common import HARNESS_DIR

HANDOFF_DIR = HARNESS_DIR / "handoff"
HANDOFF_FILE = HANDOFF_DIR / "handoff.md"


def generate_handoff():
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)

    project_root = HARNESS_DIR.parent

    commit_msg = subprocess.check_output(
        ["git", "log", "-1", "--pretty=%B"],
        text=True,
        cwd=project_root,
    ).strip()

    changed_files = subprocess.check_output(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        text=True,
        cwd=project_root,
    ).strip()

    diff_stat = subprocess.check_output(
        ["git", "diff-tree", "--no-commit-id", "--stat", "-r", "HEAD"],
        text=True,
        cwd=project_root,
    ).strip()

    content = (
        "# Session Handoff\n\n"
        f"## Last Commit\n{commit_msg}\n\n"
        f"## Changed Files\n{changed_files}\n\n"
        f"## Diff Summary\n{diff_stat}\n"
    )
    HANDOFF_FILE.write_text(content)


if __name__ == "__main__":
    generate_handoff()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd "/Users/calebngai/Desktop/Agentic-Engineering-Projects/Agent Harness/.agent-harness"
python3 -m pytest tests/test_handoff.py -v
```

Expected: 4 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add .agent-harness/scripts/handoff_cmd.py .agent-harness/tests/test_handoff.py
git commit -m "feat: add handoff_cmd.py to generate session handoff from git commit"
```

---

### Task 3: Add skills block injection to permissions.py

**Files:**
- Modify: `.agent-harness/scripts/permissions.py`
- Modify: `.agent-harness/tests/test_permissions.py`

- [ ] **Step 1: Write failing tests**

Append to `.agent-harness/tests/test_permissions.py`:

```python
# --- skills block injection ---

from scripts.permissions import inject_skills_block, SKILLS_BLOCK_START, SKILLS_BLOCK_END


def test_skills_block_created_in_all_configs(tmp_path):
    inject_skills_block(tmp_path)
    for name in ["CLAUDE.md", ".cursorrules", "AGENTS.md"]:
        content = (tmp_path / name).read_text()
        assert SKILLS_BLOCK_START in content
        assert SKILLS_BLOCK_END in content


def test_claude_md_gets_planner_skills(tmp_path):
    inject_skills_block(tmp_path)
    content = (tmp_path / "CLAUDE.md").read_text()
    assert "planner-start.md" in content
    assert "create-plan.md" in content


def test_cursorrules_gets_coder_skills(tmp_path):
    inject_skills_block(tmp_path)
    content = (tmp_path / ".cursorrules").read_text()
    assert "coder-start.md" in content
    assert "pick-up-review.md" in content
    assert "save-mistake.md" in content
    assert "query-memory.md" in content
    assert "drill-map.md" in content


def test_agents_md_gets_reviewer_skills(tmp_path):
    inject_skills_block(tmp_path)
    content = (tmp_path / "AGENTS.md").read_text()
    assert "reviewer-start.md" in content
    assert "leave-review.md" in content


def test_skills_block_idempotent(tmp_path):
    inject_skills_block(tmp_path)
    inject_skills_block(tmp_path)
    content = (tmp_path / "CLAUDE.md").read_text()
    assert content.count(SKILLS_BLOCK_START) == 1


def test_skills_block_preserved_with_existing_content(tmp_path):
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("Read bootstrap.md before each task.\n")
    inject_skills_block(tmp_path)
    content = claude_md.read_text()
    assert "Read bootstrap.md before each task." in content
    assert SKILLS_BLOCK_START in content


def test_skills_block_and_role_block_coexist(tmp_path):
    inject_role_permissions("coder", CODER_CFG, tmp_path)
    inject_skills_block(tmp_path)
    content = (tmp_path / "CLAUDE.md").read_text()
    assert BLOCK_START in content
    assert SKILLS_BLOCK_START in content
    assert content.count(SKILLS_BLOCK_START) == 1
    assert content.count(BLOCK_START) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/Users/calebngai/Desktop/Agentic-Engineering-Projects/Agent Harness/.agent-harness"
python3 -m pytest tests/test_permissions.py -v -k "skills"
```

Expected: `ImportError: cannot import name 'inject_skills_block'`

- [ ] **Step 3: Add skills injection to permissions.py**

Open `.agent-harness/scripts/permissions.py`. After the existing `AGENT_CONFIGS` constant (line 21), add:

```python
SKILLS_BLOCK_START = "<!-- agent-harness:skills:start -->"
SKILLS_BLOCK_END = "<!-- agent-harness:skills:end -->"

# Maps each agent config file to the role whose skills it should reference.
# Claude Code = planner, Cursor = coder, Codex = reviewer.
_FILE_SKILL_ROLE = {
    "CLAUDE.md": "planner",
    ".cursorrules": "coder",
    "AGENTS.md": "reviewer",
}

_SKILLS_CONTENT = {
    "planner": (
        "## Agent Harness — Skills: planner\n\n"
        "At the start of every session, read and follow "
        "`.agent-harness/skills/planner/planner-start.md`.\n\n"
        "Additional skills available when needed:\n"
        "- Create a plan: `.agent-harness/skills/planner/create-plan.md`"
    ),
    "coder": (
        "## Agent Harness — Skills: coder\n\n"
        "At the start of every session, read and follow "
        "`.agent-harness/skills/coder/coder-start.md`.\n\n"
        "Additional skills available when needed:\n"
        "- Pick up a code review: `.agent-harness/skills/coder/pick-up-review.md`\n"
        "- Save a mistake to memory: `.agent-harness/skills/coder/save-mistake.md`\n"
        "- Query memory for context: `.agent-harness/skills/coder/query-memory.md`\n"
        "- Drill into a module map: `.agent-harness/skills/coder/drill-map.md`"
    ),
    "reviewer": (
        "## Agent Harness — Skills: reviewer\n\n"
        "At the start of every session, read and follow "
        "`.agent-harness/skills/reviewer/reviewer-start.md`.\n\n"
        "When your review is complete, read and follow "
        "`.agent-harness/skills/reviewer/leave-review.md`."
    ),
}
```

Then add two functions at the bottom of the file (after `inject_role_permissions`):

```python
def _inject_skills_into_file(file_path: Path, block: str):
    """Replace or append the skills block in a config file."""
    pattern = re.compile(
        re.escape(SKILLS_BLOCK_START) + r".*?" + re.escape(SKILLS_BLOCK_END),
        re.DOTALL,
    )
    if file_path.exists():
        content = file_path.read_text()
        if pattern.search(content):
            new_content = pattern.sub(block, content)
        else:
            new_content = content.rstrip() + "\n\n" + block + "\n"
    else:
        new_content = block + "\n"
    file_path.write_text(new_content)


def inject_skills_block(project_root: Path):
    """Write role-specific skills references into each agent config file.

    CLAUDE.md  → planner skills
    .cursorrules → coder skills
    AGENTS.md  → reviewer skills
    """
    for config_name, role in _FILE_SKILL_ROLE.items():
        body = _SKILLS_CONTENT[role]
        block = f"{SKILLS_BLOCK_START}\n{body}\n{SKILLS_BLOCK_END}"
        _inject_skills_into_file(project_root / config_name, block)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd "/Users/calebngai/Desktop/Agentic-Engineering-Projects/Agent Harness/.agent-harness"
python3 -m pytest tests/test_permissions.py -v
```

Expected: all tests PASSED (existing + new skills tests)

- [ ] **Step 5: Commit**

```bash
git add .agent-harness/scripts/permissions.py .agent-harness/tests/test_permissions.py
git commit -m "feat: add skills block injection to permissions.py"
```

---

### Task 4: Update init_cmd.py

**Files:**
- Modify: `.agent-harness/scripts/init_cmd.py`

- [ ] **Step 1: Add handoff generation to POST_COMMIT_HOOK**

In `init_cmd.py`, replace the `POST_COMMIT_HOOK` string (lines 20-27) with:

```python
POST_COMMIT_HOOK = """\
# Agent Harness: incremental codebase map update
ROOT=$(git rev-parse --show-toplevel)
changed_dirs=$(git diff-tree --no-commit-id --name-only -r HEAD | cut -d/ -f1 | sort -u | tr '\\n' ' ')
if [ -n "$changed_dirs" ]; then
  cd "$ROOT"
  PYTHONPATH="$ROOT/.agent-harness" python3 .agent-harness/scripts/sync_map.py --only $changed_dirs
fi

# Agent Harness: generate session handoff
cd "$ROOT"
PYTHONPATH="$ROOT/.agent-harness" python3 .agent-harness/scripts/handoff_cmd.py
"""
```

- [ ] **Step 2: Add reviews/ and handoff/ directory creation**

In the `init_project` function, find the `dirs` list (around line 89) and add two entries:

```python
dirs = [
    HARNESS_DIR / "context" / "detail",
    HARNESS_DIR / "memory" / "entries",
    HARNESS_DIR / "rules",
    HARNESS_DIR / "logs",
    HARNESS_DIR / "reviews",
    HARNESS_DIR / "handoff",
]
```

- [ ] **Step 3: Inject skills block during init**

In `init_project`, after step 6 (the `_wire_agent_config` loop, around line 127), add:

```python
    # 7. Inject skills blocks into agent config files
    from scripts.permissions import inject_skills_block
    inject_skills_block(PROJECT_ROOT)
    print("  Injected skills blocks into agent config files")
```

Also update the final print statements to remove the manual role reminder:

```python
    print(f"\nHarness initialized for {project_type}.")
    print("Skills are pre-wired. Agents will self-guide on session start.")
```

- [ ] **Step 4: Run existing tests to confirm nothing broke**

```bash
cd "/Users/calebngai/Desktop/Agentic-Engineering-Projects/Agent Harness/.agent-harness"
python3 -m pytest tests/ -v
```

Expected: all existing tests PASSED

- [ ] **Step 5: Commit**

```bash
git add .agent-harness/scripts/init_cmd.py
git commit -m "feat: update init_cmd to create transient dirs, inject skills, extend post-commit hook"
```

---

### Task 5: Update post_session.py with deprecation notice

**Files:**
- Modify: `.agent-harness/scripts/post_session.py`

- [ ] **Step 1: Add deprecation notice**

Replace the `capture_handoff` function body with:

```python
def capture_handoff():
    """Deprecated: handoff is now generated automatically by the post-commit hook.

    This command is kept for backwards compatibility. The post-commit hook
    writes .agent-harness/handoff/handoff.md after every commit, and
    coder-start.md ingests and deletes it automatically.
    """
    print(
        "Note: 'harness post' is deprecated. The post-commit hook now generates "
        "the handoff automatically after each commit. "
        "See .agent-harness/handoff/handoff.md if a handoff was recently written."
    )
```

- [ ] **Step 2: Commit**

```bash
git add .agent-harness/scripts/post_session.py
git commit -m "chore: deprecate harness post — handoff now auto-generated by post-commit hook"
```

---

### Task 6: Write planner skill files

**Files:**
- Create: `.agent-harness/skills/planner/planner-start.md`
- Create: `.agent-harness/skills/planner/create-plan.md`

- [ ] **Step 1: Create planner-start.md**

Create `.agent-harness/skills/planner/planner-start.md`:

```markdown
# Planner Session Start

You are the **planner** for this project. Your job is to design solutions and write implementation plans. Do not write production code.

## Steps

1. Load your context by running:
   ```
   PYTHONPATH=.agent-harness python3 .agent-harness/harness prep --role planner
   ```
2. Read `.agent-harness/context/bootstrap.md` in full.
3. Check `docs/plans/` for existing plan documents. Read any that are relevant to the current task to avoid duplicating work.
4. Begin designing your solution. When you are ready to write a plan, use the `create-plan` skill.

## Constraints
- Do NOT modify or delete existing code files.
- Do NOT run `git commit`.
- Save all plan documents to `docs/plans/`.

## Other Available Skills
- **Create a plan document:** Read `.agent-harness/skills/planner/create-plan.md` and follow it.
```

- [ ] **Step 2: Create create-plan.md**

Create `.agent-harness/skills/planner/create-plan.md`:

```markdown
# Create Plan

Use this skill when you are ready to write an implementation plan.

## Steps

1. Determine a short kebab-case name for this plan (e.g., `user-auth-refactor`).
2. Create the plan file at `docs/plans/YYYY-MM-DD-<name>.md` using today's date.
3. Begin the file with this header:

   ```markdown
   # <Feature Name> Implementation Plan

   **Goal:** <one sentence describing what this builds>

   **Architecture:** <2-3 sentences about approach>

   ---
   ```

4. Write tasks as numbered sections. Each task must include:
   - Which files to create or modify (exact paths)
   - Step-by-step instructions with actual code, not descriptions
   - How to verify the task is complete

5. Save the file. It will be committed by the coder as part of their first task.

## Example Plan Structure

```markdown
### Task 1: <Component Name>

**Files:**
- Create: `src/auth/token.py`
- Modify: `src/auth/__init__.py`

- [ ] Step 1: ...
- [ ] Step 2: ...
- [ ] Commit: `git commit -m "feat: ..."`
```
```

- [ ] **Step 3: Commit**

```bash
git add .agent-harness/skills/planner/
git commit -m "feat: add planner skill files (planner-start, create-plan)"
```

---

### Task 7: Write coder skill files

**Files:**
- Create: `.agent-harness/skills/coder/coder-start.md`
- Create: `.agent-harness/skills/coder/pick-up-review.md`
- Create: `.agent-harness/skills/coder/save-mistake.md`
- Create: `.agent-harness/skills/coder/query-memory.md`
- Create: `.agent-harness/skills/coder/drill-map.md`

- [ ] **Step 1: Create coder-start.md**

Create `.agent-harness/skills/coder/coder-start.md`:

```markdown
# Coder Session Start

You are the **coder** for this project. Your job is to implement plans written by the planner and address reviews from the reviewer.

## Steps

1. Load your context:
   ```
   PYTHONPATH=.agent-harness python3 .agent-harness/harness prep --role coder
   ```
2. Read `.agent-harness/context/bootstrap.md` in full.

3. **Check for a pending handoff.** If `.agent-harness/handoff/handoff.md` exists:
   - Read it completely.
   - Save any important context to memory:
     ```
     PYTHONPATH=.agent-harness python3 .agent-harness/harness memory save "<summary of key info>" --category decision
     ```
   - Delete the handoff file:
     ```
     rm .agent-harness/handoff/handoff.md
     ```

4. **Check for a pending code review.** If any files exist in `.agent-harness/reviews/`:
   - Read `.agent-harness/skills/coder/pick-up-review.md` and follow it.

5. Check `docs/plans/` for the plan you are implementing. Read it before starting work.

6. Begin coding.

## Available Skills (invoke when needed — do not ask the user)
- When you encounter a bug or hard-won lesson: `.agent-harness/skills/coder/save-mistake.md`
- When you need context on a topic from memory: `.agent-harness/skills/coder/query-memory.md`
- When you need to understand a module's structure: `.agent-harness/skills/coder/drill-map.md`
- When a review doc appears in `.agent-harness/reviews/`: `.agent-harness/skills/coder/pick-up-review.md`

## Constraints
- Do NOT run `git push`.
- Do NOT install dependencies.
```

- [ ] **Step 2: Create pick-up-review.md**

Create `.agent-harness/skills/coder/pick-up-review.md`:

```markdown
# Pick Up Code Review

Use this skill when a review doc exists in `.agent-harness/reviews/`.

## Steps

1. List review files:
   ```
   ls .agent-harness/reviews/
   ```

2. Read the review file(s) completely. Understand all issues raised before making any changes.

3. Implement the fixes. Address each issue from the review in your changes.

4. After all fixes are implemented and verified, delete the review file:
   ```
   rm .agent-harness/reviews/<review-filename>.md
   ```
   Do NOT delete the review file before fixes are complete.

5. Commit your fixes:
   ```
   git add <changed files>
   git commit -m "fix: address code review — <brief summary>"
   ```
```

- [ ] **Step 3: Create save-mistake.md**

Create `.agent-harness/skills/coder/save-mistake.md`:

```markdown
# Save Mistake to Memory

Use this skill when you encounter a bug, unexpected behavior, or a hard-won lesson worth remembering.

## Steps

1. Write a concise one-sentence summary of the mistake and its fix. Include the cause and the correct approach.

   Example: "Calling yaml.safe_load on a non-existent file returns None, not an empty dict — always check existence first."

2. Run:
   ```
   PYTHONPATH=.agent-harness python3 .agent-harness/harness memory save "<your summary>" --category mistake --files <relevant-file-path>
   ```

   Example:
   ```
   PYTHONPATH=.agent-harness python3 .agent-harness/harness memory save "yaml.safe_load returns None for missing files, not empty dict" --category mistake --files .agent-harness/scripts/common.py
   ```

3. Continue working.
```

- [ ] **Step 4: Create query-memory.md**

Create `.agent-harness/skills/coder/query-memory.md`:

```markdown
# Query Memory

Use this skill when you need context on a topic — past decisions, known patterns, or prior mistakes — before making a significant change.

## Steps

1. Identify a keyword that describes what you need (e.g., "authentication", "database", "caching").

2. Run:
   ```
   PYTHONPATH=.agent-harness python3 .agent-harness/harness memory query "<keyword>"
   ```

   To filter by file:
   ```
   PYTHONPATH=.agent-harness python3 .agent-harness/harness memory query "<keyword>" --files <path>
   ```

3. Read the results. If an entry is directly relevant, it will show full content. Use this to inform your approach before writing code.
```

- [ ] **Step 5: Create drill-map.md**

Create `.agent-harness/skills/coder/drill-map.md`:

```markdown
# Drill Into Module Map

Use this skill when you need to understand the structure of a specific module or directory before editing it.

## Steps

1. Identify the module path you want to explore (e.g., `src/auth`, `scripts`).

2. Run:
   ```
   PYTHONPATH=.agent-harness python3 .agent-harness/harness map drill "<module-path>"
   ```

   Example:
   ```
   PYTHONPATH=.agent-harness python3 .agent-harness/harness map drill "scripts"
   ```

3. Read the output: it shows subdirectories and files within the module. Use this to locate the right file before editing.
```

- [ ] **Step 6: Commit**

```bash
git add .agent-harness/skills/coder/
git commit -m "feat: add coder skill files (coder-start, pick-up-review, save-mistake, query-memory, drill-map)"
```

---

### Task 8: Write reviewer skill files

**Files:**
- Create: `.agent-harness/skills/reviewer/reviewer-start.md`
- Create: `.agent-harness/skills/reviewer/leave-review.md`

- [ ] **Step 1: Create reviewer-start.md**

Create `.agent-harness/skills/reviewer/reviewer-start.md`:

```markdown
# Reviewer Session Start

You are the **reviewer** for this project. Your job is to review recent code changes for correctness, conventions, and quality. You may fix minor issues directly; leave a review doc for anything requiring coder attention.

## Steps

1. Load your context:
   ```
   PYTHONPATH=.agent-harness python3 .agent-harness/harness prep --role reviewer
   ```
2. Read `.agent-harness/context/bootstrap.md` in full.

3. Read the recent diff to understand what changed:
   ```
   git diff HEAD~1 HEAD
   ```
   Or for a larger review window:
   ```
   git log --oneline -10
   git diff <base-sha> HEAD
   ```

4. Check against known conventions:
   ```
   PYTHONPATH=.agent-harness python3 .agent-harness/harness rules check
   ```

5. Check for known mistakes relevant to changed files:
   ```
   PYTHONPATH=.agent-harness python3 .agent-harness/harness mistakes <changed-file-paths>
   ```

6. Review the code. When your review is complete, follow `.agent-harness/skills/reviewer/leave-review.md`.

## Constraints
- Do NOT create new files (other than the review doc).
- Do NOT run `git commit`.
- Minor self-contained fixes may be applied directly without a review doc.
```

- [ ] **Step 2: Create leave-review.md**

Create `.agent-harness/skills/reviewer/leave-review.md`:

```markdown
# Leave Code Review

Use this skill when your review is complete and issues need coder attention.

If there are no issues requiring coder action, skip this skill — no review doc is needed.

## Steps

1. Generate a timestamp for the filename:
   ```
   date +%Y%m%d-%H%M%S
   ```

2. Create the review file at `.agent-harness/reviews/review-<timestamp>.md`.

3. Write the review using this structure:

   ```markdown
   # Code Review — <date>

   ## Summary
   <1-2 sentences describing what was reviewed>

   ## Issues

   ### Issue 1: <short title>
   **File:** `<path>:<line>`
   **Severity:** error | warning | suggestion
   **Description:** <what is wrong>
   **Fix:** <what the coder should do>

   ### Issue 2: ...

   ## Passed
   <Brief note on what looks good — optional>
   ```

4. Save the file. Do NOT commit it — it is gitignored and will be deleted by the coder after they apply the fixes.
```

- [ ] **Step 3: Commit**

```bash
git add .agent-harness/skills/reviewer/
git commit -m "feat: add reviewer skill files (reviewer-start, leave-review)"
```

---

### Task 9: Wire skills blocks into current agent config files

The `inject_skills_block` function will be called automatically by `harness init` for new projects. For this repo (which is already initialized), call it once manually.

**Files:**
- Modify: `CLAUDE.md`, `.cursorrules`, `AGENTS.md` (via script)

- [ ] **Step 1: Run skills injection on the current project**

```bash
cd "/Users/calebngai/Desktop/Agentic-Engineering-Projects/Agent Harness"
PYTHONPATH=.agent-harness python3 -c "
from scripts.permissions import inject_skills_block
from pathlib import Path
inject_skills_block(Path('.'))
print('Skills blocks injected.')
"
```

- [ ] **Step 2: Verify each file has the skills block**

```bash
grep -l "agent-harness:skills:start" CLAUDE.md .cursorrules AGENTS.md
```

Expected: all three filenames printed.

- [ ] **Step 3: Verify CLAUDE.md references planner skills**

```bash
grep "planner-start" CLAUDE.md
```

Expected: one line containing `planner-start.md`

- [ ] **Step 4: Verify .cursorrules references coder skills**

```bash
grep "coder-start" .cursorrules
```

Expected: one line containing `coder-start.md`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md .cursorrules AGENTS.md
git commit -m "chore: inject skills blocks into agent config files"
```

---

### Task 10: Install handoff hook in this repo

The post-commit hook currently only runs map sync. Update it to also call handoff_cmd.py.

**Files:**
- Modify: `.git/hooks/post-commit` (if it exists) — otherwise create it

- [ ] **Step 1: Check current post-commit hook**

```bash
cat "/Users/calebngai/Desktop/Agentic-Engineering-Projects/Agent Harness/.git/hooks/post-commit" 2>/dev/null || echo "No post-commit hook"
```

- [ ] **Step 2: Append handoff generation to the hook**

If the hook exists and does NOT already contain `handoff_cmd`:

```bash
cat >> "/Users/calebngai/Desktop/Agentic-Engineering-Projects/Agent Harness/.git/hooks/post-commit" << 'EOF'

# Agent Harness: generate session handoff
ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"
PYTHONPATH="$ROOT/.agent-harness" python3 .agent-harness/scripts/handoff_cmd.py
EOF
```

If no hook exists:

```bash
cat > "/Users/calebngai/Desktop/Agentic-Engineering-Projects/Agent Harness/.git/hooks/post-commit" << 'EOF'
#!/bin/bash
# Agent Harness: generate session handoff
ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"
PYTHONPATH="$ROOT/.agent-harness" python3 .agent-harness/scripts/handoff_cmd.py
EOF
chmod +x "/Users/calebngai/Desktop/Agentic-Engineering-Projects/Agent Harness/.git/hooks/post-commit"
```

- [ ] **Step 3: Verify the hook is executable**

```bash
ls -la "/Users/calebngai/Desktop/Agentic-Engineering-Projects/Agent Harness/.git/hooks/post-commit"
```

Expected: file exists with `x` permission bits.

- [ ] **Step 4: Test by making a test commit and checking handoff**

```bash
cd "/Users/calebngai/Desktop/Agentic-Engineering-Projects/Agent Harness"
# Make a trivial change
echo "# test" >> /tmp/test-hook.txt && git add /tmp/test-hook.txt 2>/dev/null || true
# Check handoff after next real commit instead — just verify the script runs directly
PYTHONPATH=.agent-harness python3 .agent-harness/scripts/handoff_cmd.py
cat .agent-harness/handoff/handoff.md
```

Expected: handoff.md exists and contains the last commit message and changed files.

---

## Verification Checklist

- [ ] `.gitignore` contains `.agent-harness/reviews/` and `.agent-harness/handoff/`
- [ ] `handoff_cmd.py` exists and all 4 tests pass
- [ ] `permissions.py` exports `inject_skills_block`, `SKILLS_BLOCK_START`, `SKILLS_BLOCK_END`
- [ ] All permissions tests pass (existing + 7 new skills tests)
- [ ] `CLAUDE.md` contains skills block referencing `planner-start.md`
- [ ] `.cursorrules` contains skills block referencing `coder-start.md` and all 4 coder skills
- [ ] `AGENTS.md` contains skills block referencing `reviewer-start.md` and `leave-review.md`
- [ ] 9 skill markdown files exist in `.agent-harness/skills/`
- [ ] Post-commit hook calls `handoff_cmd.py`
- [ ] `.agent-harness/handoff/handoff.md` is generated by `handoff_cmd.py` and is gitignored
- [ ] All tests pass: `cd .agent-harness && python3 -m pytest tests/ -v`
