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
