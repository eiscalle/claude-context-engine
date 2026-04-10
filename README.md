# Claude Context Engine

**Your AI conversations + project docs compile themselves into a searchable knowledge base.**

Adapted from [Karpathy's LLM Knowledge Base](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) architecture. Unlike the original which clips web articles, this system ingests **two sources**: your Claude Code conversations (captured automatically via hooks) and your project's static files -- design specs, architecture docs, governance rules, auto-memories, and any external articles you drop into the sources folder. The [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) extracts decisions, lessons learned, patterns, and gotchas, then compiles them into structured, cross-referenced knowledge articles. Retrieval uses a simple index file instead of RAG -- no vector database, no embeddings, just markdown.

Forked from [coleam00/claude-memory-compiler](https://github.com/coleam00/claude-memory-compiler) and significantly extended.

## What's New vs. Upstream

| Feature | Upstream | This Fork |
|---------|----------|-----------|
| **Source ingestion** | Conversations only | Conversations + external files via `sources.yaml` |
| **Handler system** | None | Pluggable handlers (markdown built-in, PDF/URL planned) |
| **Resume-here state** | None | `wip.md` extracted from sessions, injected on start |
| **Drop zone** | None | `sources/articles/`, `sources/notes/`, `sources/pdfs/` |
| **Knowledge location** | Inside `.claude/` | Project root (`knowledge/`) -- Claude Code blocks writes inside `.claude/` |
| **Exclude patterns** | Broken for external paths | Fixed (`fnmatch` against filenames) |
| **State schema** | Flat `ingested` dict | Split `ingested_daily` + `ingested_sources` with auto-migration |
| **Permission mode** | `acceptEdits` | `bypassPermissions` (required for unattended ingestion) |
| **Auto-memory ingestion** | None | Symlink `.claude/memory/` and add to `sources.yaml` |

## Architecture

```
                       SESSION LIFECYCLE
                       =================

  ┌─────────────┐     SessionStart hook      ┌──────────────────┐
  │ Claude Code  │◄─── injects index.md ─────│ session-start.py │
  │   session    │     + wip.md + recent log  └──────────────────┘
  └──────┬───────┘
         │ SessionEnd / PreCompact hook
         ▼
  ┌──────────────┐     background spawn      ┌─────────────┐
  │session-end.py│──────────────────────►    │  flush.py   │
  └──────────────┘   (detached process)       └──────┬──────┘
                                                     │
                                  ┌──────────────────┼──────────────────┐
                                  ▼                  ▼                  ▼
                           Agent SDK call    daily/YYYY-MM-DD.md   wip.md
                           (extract knowledge)                   (resume-here)
                                                     │
                                                     │ after 6 PM
                                                     ▼
                                              ┌─────────────┐
                                              │ compile.py  │──► knowledge/
                                              └─────────────┘


                       SOURCE INGESTION
                       ================

  sources.yaml ──► ingest.py ──► source_handlers/ ──► Agent SDK ──► knowledge/
       │                              │
       ├── design-specs/*.md          ├── markdown.py (built-in)
       ├── implementation-plans/*.md  ├── pdf.py      (planned)
       ├── governance (CLAUDE.md)     └── url.py      (planned)
       ├── captured-memory/*.md
       └── sources/articles/*.md
```

## Quick Start

### 1. Fork and clone

```bash
git clone https://github.com/YOUR_USER/claude-context-engine .claude/memory-compiler
cd .claude/memory-compiler
uv sync
```

### 2. Configure hooks

Merge into your project's `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "uv run --directory .claude/memory-compiler python .claude/memory-compiler/hooks/session-start.py",
        "timeout": 15
      }]
    }],
    "PreCompact": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "uv run --directory .claude/memory-compiler python .claude/memory-compiler/hooks/session-end.py",
        "timeout": 10
      }]
    }],
    "SessionEnd": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "uv run --directory .claude/memory-compiler python .claude/memory-compiler/hooks/session-end.py",
        "timeout": 10
      }]
    }]
  }
}
```

### 3. Set up source ingestion

```bash
cp sources.yaml.example sources.yaml
# Edit sources.yaml: point globs at your project's docs, specs, memories
uv run python scripts/ingest.py --dry-run   # preview
uv run python scripts/ingest.py             # run
```

### 4. Use it

Sessions accumulate automatically. After 6 PM, compilation triggers on next flush. Knowledge base grows with every session and every `ingest.py` run.

## How It Works

```
Conversation -> SessionEnd/PreCompact hooks -> flush.py extracts knowledge
    -> daily/YYYY-MM-DD.md -> compile.py -> knowledge/concepts/, connections/, qa/
        -> SessionStart hook injects index + wip.md -> cycle repeats

Source files -> sources.yaml -> ingest.py -> knowledge/concepts/, connections/
    -> same index, same articles, cross-linked with session knowledge
```

- **Hooks** capture conversations automatically (session end + pre-compaction safety net)
- **flush.py** extracts knowledge via Agent SDK, writes daily log + wip.md resume-here state
- **compile.py** turns daily logs into organized concept articles with cross-references
- **ingest.py** turns source files (specs, docs, memories, articles) into the same knowledge base
- **query.py** answers questions using index-guided retrieval (no RAG needed at personal scale)
- **lint.py** runs 8 health checks (broken links, orphans, contradictions, staleness, uningested sources)

## Key Commands

```bash
# Session logs -> knowledge
uv run python scripts/compile.py                    # compile new daily logs
uv run python scripts/compile.py --all              # force recompile

# Source files -> knowledge
uv run python scripts/ingest.py                     # ingest new/changed sources
uv run python scripts/ingest.py --all               # force re-ingest everything
uv run python scripts/ingest.py --source design-specs  # one group only
uv run python scripts/ingest.py --dry-run --verbose

# Ask the knowledge base
uv run python scripts/query.py "question"
uv run python scripts/query.py "question" --file-back  # save answer as article

# Health checks
uv run python scripts/lint.py                       # all checks
uv run python scripts/lint.py --structural-only     # free structural checks only
```

## Configuration: sources.yaml

```yaml
version: 1

sources:
  - id: design-specs           # Unique identifier
    type: markdown             # Handler type (markdown now; pdf, url planned)
    include:                   # Globs relative to memory-compiler root
      - "../../docs/specs/*.md"
    exclude:                   # Filename patterns (fnmatch)
      - "**/*DRAFT.md"
    category: design-specs     # Tag on generated articles
    description: "Project design specs"

  - id: external-articles
    type: markdown
    include:
      - "sources/articles/*.md"   # Drop zone
      - "sources/notes/*.md"
    category: external
    description: "Web clippings, research notes"
```

### Adding a handler

1. Create `scripts/source_handlers/your_type.py`
2. Define `extract(path: Path) -> SourceDocument`
3. Call `register("your_type", extract)`
4. Import in `scripts/source_handlers/__init__.py`

## Portability

Each project gets its own clone with its own `sources.yaml` and isolated `knowledge/` directory:

1. Clone into `.claude/memory-compiler/`
2. `uv sync`
3. Copy `sources.yaml.example` -> `sources.yaml`, customize globs
4. Merge hooks into `.claude/settings.json`
5. `uv run python scripts/ingest.py`

The `knowledge/` output lives at the **project root** (not inside `.claude/`) because Claude Code blocks Agent SDK writes inside `.claude/`.

## Memory Symlink

Claude Code stores auto-memory outside the project. To ingest it:

```bash
# Windows
mklink /J .claude\memory %USERPROFILE%\.claude\projects\<slug>\memory

# Mac/Linux
ln -s ~/.claude/projects/<slug>/memory .claude/memory
```

Then add a `captured-memory` source group pointing at `../../.claude/memory/*.md`.

## Why No RAG?

Karpathy's insight: at personal scale (50-500 articles), the LLM reading a structured `index.md` outperforms vector similarity. The LLM understands what you're really asking; cosine similarity just finds similar words. RAG becomes necessary at ~2,000+ articles when the index exceeds the context window.

## Cost

All operations use the Claude Agent SDK on your existing Claude subscription (Max, Team, or Enterprise). No separate API credits needed.

## Obsidian Integration

The knowledge base is pure markdown with `[[wikilinks]]`. Point an Obsidian vault at `knowledge/` for graph view, backlinks, and search.

## Technical Reference

See **[AGENTS.md](AGENTS.md)** for the complete technical reference: article formats, hook architecture, script internals, source handler API, cross-platform details, and customization options.

## Credits

- Forked from [coleam00/claude-memory-compiler](https://github.com/coleam00/claude-memory-compiler) by Cole Medin
- Inspired by [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- Built on the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) by Anthropic
