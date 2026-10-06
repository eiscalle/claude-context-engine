"""
Compile daily conversation logs into structured knowledge articles.

This is the "LLM compiler" - it reads daily logs (source code) and produces
organized knowledge articles (the executable).

Usage:
    uv run python compile.py                    # compile new/changed logs only
    uv run python compile.py --all              # force recompile everything
    uv run python compile.py --file daily/2026-04-01.md  # compile a specific log
    uv run python compile.py --dry-run          # show what would be compiled
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from compile_lock import compilation_lock
from config import (
    AGENT_CLI_ARGS,
    AGENT_MODEL,
    AGENTS_FILE,
    CONCEPTS_DIR,
    CONNECTIONS_DIR,
    DAILY_DIR,
    FILE_TOOLS,
    KNOWLEDGE_DIR,
    _PROJECT_ROOT,
    _STATE_DIR,
    now_iso,
)
from utils import (
    file_hash,
    list_raw_files,
    list_wiki_articles,
    load_state,
    migrate_state_schema,
    read_wiki_index,
    save_state,
)
from compile_truth import COMPILED_TRUTH_FILE, compile_truth as regenerate_truth


async def compile_daily_log(log_path: Path, state: dict) -> float | None:
    """Compile one daily log and return its API cost, or ``None`` on failure."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        query,
    )

    log_content = log_path.read_text(encoding="utf-8")
    schema = AGENTS_FILE.read_text(encoding="utf-8")
    wiki_index = read_wiki_index()

    # Read compiled truth — dense summary of all current knowledge (zero-cost artifact)
    compiled_truth = ""
    if COMPILED_TRUTH_FILE.exists():
        compiled_truth = COMPILED_TRUTH_FILE.read_text(encoding="utf-8")

    timestamp = now_iso()

    prompt = f"""You are a knowledge compiler. Your job is to read a daily conversation log
and extract knowledge into structured wiki articles.

## Schema (AGENTS.md)

{schema}

## Current Wiki Index

{wiki_index}

## Current Knowledge (compiled truth)

{compiled_truth if compiled_truth else "(No compiled truth yet — run compile_truth.py first)"}

## Daily Log to Compile

**File:** {log_path.name}

{log_content}

## Your Task

Read the daily log above and compile it into wiki articles following the schema exactly.

### Rules:

1. **Extract key concepts** - Identify 3-7 distinct concepts worth their own article
2. **Create concept articles** in `knowledge/concepts/` - One .md file per concept
   - Use the Truth + Timeline format from AGENTS.md:
     * `## Truth` section: current facts only, no narrative or provenance
     * `### Key Points` under Truth: 3-5 self-contained factual bullets
     * `### Related Concepts` under Truth: [[wikilinks]] with one-line descriptions
     * `---` horizontal rule separator
     * `## Timeline` section: per-source entries documenting what was learned and when
   - Include `sources:` in frontmatter pointing to the daily log file
   - Write Truth in encyclopedia style — dense, factual, no "we discovered"
3. **Create connection articles** in `knowledge/connections/` if this log reveals non-obvious
   relationships between 2+ existing concepts
4. **Update existing articles** if this log adds new information to concepts already in the wiki
   - Read the existing article, add the new information, add the source to frontmatter
5. **Update knowledge/index.md** - Add new entries to the table
   - Each entry: `| [[path/slug]] | One-line summary | source-file | {timestamp[:10]} |`
6. **Append to knowledge/log.md** - Add a timestamped entry:
   ```
   ## [{timestamp}] compile | {log_path.name}
   - Source: daily/{log_path.name}
   - Articles created: [[concepts/x]], [[concepts/y]]
   - Articles updated: [[concepts/z]] (if any)
   ```
7. **Use tools to check existing articles** — The wiki index above lists every article
   with its path and one-line summary. Before creating a new article, check the index
   for duplicates or near-duplicates. To update an existing article, use the Read tool
   to fetch it first, then Edit to modify it. Use Grep to search for related concepts
   when adding [[wikilinks]].

### File paths:
- Write concept articles to: {CONCEPTS_DIR}
- Write connection articles to: {CONNECTIONS_DIR}
- Update index at: {KNOWLEDGE_DIR / "index.md"}
- Append log at: {KNOWLEDGE_DIR / "log.md"}

### Quality standards:
- Every article must have complete YAML frontmatter
- Every article must link to at least 2 other articles via [[wikilinks]]
- Key Points section should have 3-5 bullet points
- Details section should have 2+ paragraphs
- Related Concepts section should have 2+ entries
- Sources section should cite the daily log with specific claims extracted
"""

    cost = 0.0
    completed = False

    try:
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                cwd=str(_PROJECT_ROOT),
                system_prompt={"type": "preset", "preset": "claude_code"},
                tools=FILE_TOOLS,
                allowed_tools=FILE_TOOLS,
                permission_mode="bypassPermissions",
                extra_args=AGENT_CLI_ARGS,
                max_turns=30,
                model=AGENT_MODEL,
            ),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        pass  # compilation output - LLM writes files directly
            elif isinstance(message, ResultMessage):
                if message.is_error:
                    detail = message.result or "; ".join(message.errors or []) or message.subtype
                    print(f"  Error: {detail}")
                    return None
                cost = message.total_cost_usd or 0.0
                completed = True
                print(f"  Cost: ${cost:.4f}")
    except Exception as e:
        print(f"  Error: {e}")
        return None

    if not completed:
        print("  Error: Agent SDK returned no successful result")
        return None

    # Update state only after a successful ResultMessage.
    rel_path = log_path.name
    state.setdefault("ingested_daily", {})[rel_path] = {
        "hash": file_hash(log_path),
        "compiled_at": now_iso(),
        "cost_usd": cost,
    }
    state["total_cost"] = state.get("total_cost", 0.0) + cost
    save_state(state)

    return cost


def _run(args: argparse.Namespace) -> None:
    """Compile the logs selected by parsed command-line arguments."""
    state = load_state()
    state = migrate_state_schema(state)

    # Determine which files to compile
    if args.file:
        target = Path(args.file)
        if not target.is_absolute():
            target = DAILY_DIR / target.name
        if not target.exists():
            # Try resolving relative to data dir
            target = _PROJECT_ROOT / args.file
        if not target.exists():
            print(f"Error: {args.file} not found")
            sys.exit(1)
        to_compile = [target]
    else:
        all_logs = list_raw_files()
        if args.all:
            to_compile = all_logs
        else:
            to_compile = []
            for log_path in all_logs:
                rel = log_path.name
                prev = state.get("ingested_daily", {}).get(rel, {})
                if not prev or prev.get("hash") != file_hash(log_path):
                    to_compile.append(log_path)

    if not to_compile:
        print("Nothing to compile - all daily logs are up to date.")
        return

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Files to compile ({len(to_compile)}):")
    for f in to_compile:
        print(f"  - {f.name}")

    if args.dry_run:
        return

    # Compile each file sequentially
    total_cost = 0.0
    succeeded = 0
    failed = 0
    for i, log_path in enumerate(to_compile, 1):
        print(f"\n[{i}/{len(to_compile)}] Compiling {log_path.name}...")
        cost = asyncio.run(compile_daily_log(log_path, state))
        if cost is None:
            failed += 1
            print("  Failed; state not updated.")
            continue
        total_cost += cost
        succeeded += 1
        print("  Done.")

    articles = list_wiki_articles()
    regenerate_truth()
    print(f"\nCompilation complete. Total cost: ${total_cost:.2f}")
    print(f"Logs: {succeeded} succeeded, {failed} failed")
    print(f"Knowledge base: {len(articles)} articles")

    # Notify (non-fatal if it fails)
    try:
        from notify import notify

        notify(
            "Context Engine",
            f"Compile: ${total_cost:.2f} ({succeeded}/{len(to_compile)} files) | "
            f"KB: {len(articles)} articles",
        )
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile daily logs into knowledge articles")
    parser.add_argument("--all", action="store_true", help="Force recompile all logs")
    parser.add_argument("--file", type=str, help="Compile a specific daily log file")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be compiled")
    args = parser.parse_args()

    if args.dry_run:
        _run(args)
        return

    lock_path = _STATE_DIR / "compile.lock"
    with compilation_lock(lock_path) as acquired:
        if not acquired:
            print("Compilation already running; skipping duplicate request.")
            return
        _run(args)


if __name__ == "__main__":
    main()
