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
