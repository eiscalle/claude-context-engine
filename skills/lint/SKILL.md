---
description: Run health checks on the knowledge base. Use when the user wants to check for broken links, orphan pages, stale articles, or contradictions.
---

Run the wiki lint script to check knowledge base health.

Arguments are passed directly to the script:
- `--structural-only` — free checks only (no LLM calls)
- Default runs all checks including contradiction detection (costs ~$0.15-0.25)

Command: `wiki-run "${CLAUDE_PLUGIN_ROOT}/scripts/lint.py" $ARGUMENTS`
