"""
Ingest static source files into the knowledge base.

Reads sources.yaml, resolves file globs, dispatches to type-specific handlers,
and feeds each source file to the Claude Agent SDK for extraction into
knowledge/concepts/ and knowledge/connections/ articles.

Usage:
    uv run python ingest.py                     # incremental (new/changed only)
    uv run python ingest.py --all               # force re-ingest everything
    uv run python ingest.py --source design-specs  # only one source group
    uv run python ingest.py --dry-run           # show what would happen
    uv run python ingest.py --verbose           # print per-file decisions
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from config import AGENTS_FILE, CONCEPTS_DIR, CONNECTIONS_DIR, KNOWLEDGE_DIR, now_iso
from source_handlers import get_handler
from utils import (
    SourceGroup,
    file_hash,
    list_wiki_articles,
    load_sources_config,
    load_state,
    migrate_state_schema,
    read_wiki_index,
    resolve_source_files,
    save_state,
)
from compile_truth import compile_truth as regenerate_truth, COMPILED_TRUTH_FILE

from config import _DATA_DIR


def source_state_key(group: SourceGroup, file_path: Path) -> str:
    """Build the state.json key for a source file: '{source_id}/{filename}'."""
    return f"{group.id}/{file_path.name}"


def collect_files_to_ingest(
    groups: list[SourceGroup],
    state: dict,
    force_all: bool = False,
    only_source: str | None = None,
    verbose: bool = False,
) -> list[tuple[SourceGroup, Path]]:
    """Resolve all source files, filter to new/changed ones."""
    ingested_sources = state.get("ingested_sources", {})
    to_ingest: list[tuple[SourceGroup, Path]] = []

    for group in groups:
        if only_source and group.id != only_source:
            continue

        files = resolve_source_files(group)
        if verbose:
            print(f"  {group.id}: {len(files)} files resolved")

        for fpath in files:
            key = source_state_key(group, fpath)
            current_hash = file_hash(fpath)

            if not force_all:
                prev = ingested_sources.get(key, {})
                if prev.get("hash") == current_hash:
                    if verbose:
                        print(f"    SKIP (unchanged): {fpath.name}")
                    continue

            to_ingest.append((group, fpath))
            if verbose:
                print(f"    QUEUE: {fpath.name}")

    return to_ingest


async def ingest_source_file(
    group: SourceGroup,
    file_path: Path,
    state: dict,
) -> float:
    """Ingest a single source file into the knowledge base.

    Returns the API cost of the ingestion.
    """
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        query,
    )

    handler = get_handler(group.type)
    doc = handler(file_path)

    schema = AGENTS_FILE.read_text(encoding="utf-8")
    wiki_index = read_wiki_index()

    compiled_truth = ""
    if COMPILED_TRUTH_FILE.exists():
        compiled_truth = COMPILED_TRUTH_FILE.read_text(encoding="utf-8")

    timestamp = now_iso()
    rel_source = f"sources/{group.id}/{file_path.name}"

    prompt = f"""You are a knowledge compiler. Your job is to read a source document and
extract knowledge into structured wiki articles.

## Schema (AGENTS.md)

{schema}

## Current Wiki Index

{wiki_index}

## Current Knowledge (compiled truth)

{compiled_truth if compiled_truth else "(No compiled truth yet — run compile_truth.py first)"}

## Source Document to Ingest

**File:** {file_path.name}
**Source ID:** {group.id}
**Category:** {group.category}
**Type:** {group.type}

{doc.content}

## Your Task

Read the source document above and compile it into wiki articles following the schema.

This is a **{group.category}** source ({group.description}). Unlike daily conversation
logs, this is a structured document — extract its key concepts, decisions, and
architectural patterns.

### Rules:

1. **Extract key concepts** — Identify 2-5 distinct concepts worth their own article.
   A large design spec may warrant more; a small governance doc may warrant 1-2.
2. **Create concept articles** in `knowledge/concepts/` — One .md file per concept
   - Use the Truth + Timeline format from AGENTS.md:
     * `## Truth` section: current facts only, no narrative or provenance
     * `### Key Points` under Truth: 3-5 self-contained factual bullets
     * `### Related Concepts` under Truth: [[wikilinks]] with one-line descriptions
     * `---` horizontal rule separator
     * `## Timeline` section: per-source entries documenting what was learned and when
   - Include `sources:` in frontmatter pointing to `{rel_source}`
   - Add `source_type: {group.type}` and `source_category: {group.category}` to frontmatter
   - Write Truth in encyclopedia style — dense, factual, no "we discovered"
3. **Create connection articles** in `knowledge/connections/` if this source reveals
   non-obvious relationships between 2+ existing concepts in the wiki
4. **Update existing articles** if this source adds new information to concepts already
   in the wiki — read the existing article, merge in the new information, add this
   source to the frontmatter `sources:` list
5. **Update knowledge/index.md** — Add new entries to the table
   - Each entry: `| [[path/slug]] | One-line summary | {rel_source} | {timestamp[:10]} |`
6. **Append to knowledge/log.md** — Add a timestamped entry:
   ```
   ## [{timestamp}] ingest | {file_path.name}
   - Source: {rel_source}
   - Category: {group.category}
   - Articles created: [[concepts/x]], [[concepts/y]]
   - Articles updated: [[concepts/z]] (if any)
   ```
7. **Use tools to check existing articles** — The wiki index above lists every article
   with its path and one-line summary. Before creating a new article, check the index
   for duplicates or near-duplicates. To update an existing article, use the Read tool
   to fetch it first, then Edit to modify it. Use Grep to search for related concepts
   when adding [[wikilinks]]. Prefer UPDATING an existing article over creating a
   near-duplicate.

### Quality standards:
- Every article must have complete YAML frontmatter (title, aliases, tags, sources,
  source_type, source_category, created, updated)
- Every article must link to at least 2 other articles via [[wikilinks]]
- Key Points section should have 3-5 bullet points
- Details section should have 2+ paragraphs
- Prefer UPDATING an existing article over creating a near-duplicate
- When multiple source files cover the same topic, the resulting article should
  SYNTHESIZE all of them, not just reflect the latest one

### File paths (use these EXACT paths):
- Write concept articles to: {CONCEPTS_DIR}
- Write connection articles to: {CONNECTIONS_DIR}
- Update index at: {KNOWLEDGE_DIR / 'index.md'}
- Append log at: {KNOWLEDGE_DIR / 'log.md'}
"""

    cost = 0.0

    try:
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                cwd=str(_DATA_DIR),
                system_prompt={"type": "preset", "preset": "claude_code"},
                allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
                permission_mode="bypassPermissions",
                max_turns=30,
            ),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        pass
            elif isinstance(message, ResultMessage):
                cost = message.total_cost_usd or 0.0
                print(f"  Cost: ${cost:.4f}")
    except Exception as e:
        print(f"  Error: {e}")
        return 0.0

    key = source_state_key(group, file_path)
    state["ingested_sources"][key] = {
        "hash": file_hash(file_path),
        "ingested_at": now_iso(),
        "cost_usd": cost,
        "source_id": group.id,
    }
    state["total_cost"] = state.get("total_cost", 0.0) + cost
    save_state(state)

    return cost


def main():
    parser = argparse.ArgumentParser(description="Ingest source files into knowledge base")
    parser.add_argument("--all", action="store_true", help="Force re-ingest all sources")
    parser.add_argument("--source", type=str, help="Only ingest a specific source group by id")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be ingested")
    parser.add_argument("--verbose", action="store_true", help="Print per-file decisions")
    args = parser.parse_args()

    state = load_state()
    state = migrate_state_schema(state)
    save_state(state)

    groups = load_sources_config()
    if not groups:
        print("No sources.yaml found or no source groups defined.")
        print("Copy sources.yaml.example to sources.yaml and customize it.")
        return

    if args.source:
        valid_ids = [g.id for g in groups]
        if args.source not in valid_ids:
            print(f"Error: source group '{args.source}' not found.")
            print(f"Available: {', '.join(valid_ids)}")
            sys.exit(1)

    to_ingest = collect_files_to_ingest(
        groups, state,
        force_all=args.all,
        only_source=args.source,
        verbose=args.verbose,
    )

    if not to_ingest:
        print("Nothing to ingest — all source files are up to date.")
        return

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Files to ingest ({len(to_ingest)}):")
    for group, fpath in to_ingest:
        print(f"  [{group.id}] {fpath.name}")

    if args.dry_run:
        return

    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    CONCEPTS_DIR.mkdir(parents=True, exist_ok=True)
    CONNECTIONS_DIR.mkdir(parents=True, exist_ok=True)

    total_cost = 0.0
    for i, (group, fpath) in enumerate(to_ingest, 1):
        print(f"\n[{i}/{len(to_ingest)}] Ingesting [{group.id}] {fpath.name}...")
        cost = asyncio.run(ingest_source_file(group, fpath, state))
        total_cost += cost
        print(f"  Done.")

    articles = list_wiki_articles()
    regenerate_truth()
    print(f"\nIngestion complete. Total cost: ${total_cost:.2f}")
    print(f"Knowledge base: {len(articles)} articles")


if __name__ == "__main__":
    main()
