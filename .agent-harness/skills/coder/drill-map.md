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
