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
