---
description: Query the knowledge base with a natural language question. Use when the user wants to search or ask questions about their accumulated knowledge.
---

Run the wiki query script for index-guided retrieval from the knowledge base.

Arguments are passed directly to the script:
- First argument is the question (in quotes)
- `--file-back` — save the answer as a knowledge article

Command: `wiki-run "${CLAUDE_PLUGIN_ROOT}/scripts/query.py" $ARGUMENTS`
