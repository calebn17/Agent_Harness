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
