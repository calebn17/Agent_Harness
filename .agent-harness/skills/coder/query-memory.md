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
