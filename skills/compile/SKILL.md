---
description: Compile daily conversation logs into knowledge base articles. Use when the user wants to compile, build, or update their knowledge base.
---

Run the wiki compilation script to process daily logs into knowledge articles.

Arguments are passed directly to the script:
- `--all` — recompile everything (ignore hash cache)
- `--file daily/YYYY-MM-DD.md` — compile a specific daily log

Command: `wiki-run "${CLAUDE_PLUGIN_ROOT}/scripts/compile.py" $ARGUMENTS`
