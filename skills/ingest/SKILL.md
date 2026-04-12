---
description: Ingest external source documents into the knowledge base. Use when the user wants to import docs, specs, or markdown files from sources.yaml.
---

Run the wiki ingestion script to process external sources defined in `sources.yaml` (in the current project directory).

Arguments are passed directly to the script:
- `--all` — re-ingest everything
- `--source <id>` — ingest a specific source
- `--dry-run --verbose` — preview without changes

Command: `wiki-run "${CLAUDE_PLUGIN_ROOT}/scripts/ingest.py" $ARGUMENTS`
