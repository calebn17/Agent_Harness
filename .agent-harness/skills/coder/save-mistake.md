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
