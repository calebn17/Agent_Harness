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
