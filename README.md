# Wiki — Claude Code Plugin

**Your AI conversations compile themselves into a searchable personal knowledge base.**

A Claude Code plugin that automatically captures learning from every coding session and compiles it into structured, cross-referenced knowledge articles. Uses index-guided retrieval instead of RAG — no vector database, no embeddings, just markdown and an index the LLM can reason over.

Forked from [coleam00/claude-memory-compiler](https://github.com/coleam00/claude-memory-compiler), inspired by [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). Rewritten as a Claude Code plugin for one-command install and portability across all projects.

## Install

### From local directory

```bash
git clone https://github.com/eiscalle/claude-context-engine
claude --plugin-dir ./claude-context-engine
```

### From marketplace

```bash
/plugin marketplace add eiscalle/claude-context-engine
/plugin install wiki@claude-context-engine
```

### Configure on first use

When you enable the plugin, Claude Code will prompt for two settings:

| Setting | Description | Default |
|---------|-------------|---------|
| `data_dir` | Where to store the knowledge base | `~/wiki` |
| `timezone` | Your local timezone | `America/Chicago` |

The data directory will be created automatically on the first session start.

### Prerequisites

- [uv](https://docs.astral.sh/uv/) package manager
- Claude Code with Agent SDK access (Max, Team, or Enterprise subscription)

## How It Works

```
Session starts  ──► session_start.py injects knowledge context
                    (index + compiled truth + wip.md + recent log)

Session runs    ──► you work as usual

Session ends    ──► session_end.py captures transcript
                    ──► flush.py (background) extracts knowledge ──► daily/YYYY-MM-DD.md
                                                                 ──► wip.md (resume-here)
                    ──► after 6 PM: compile.py auto-triggers
                        ──► knowledge/concepts/, connections/
                        ──► compile_truth.py ──► compiled-truth.md (zero cost)

Next session    ──► cycle repeats with fresh knowledge
```

Source files can also be ingested via `/wiki:ingest` from a project's `sources.yaml`.

## Plugin Skills

| Skill | What it does |
|-------|-------------|
| `/wiki:init` | Initialize knowledge base — explore project, create articles |
| `/wiki:compile` | Compile daily logs into knowledge articles |
| `/wiki:ingest` | Ingest external sources from `sources.yaml` |
| `/wiki:query` | Query knowledge base with natural language |
| `/wiki:lint` | Run health checks (broken links, orphans, staleness) |
| `/wiki:cost-report` | Show API spending summary |

### Getting started

Run `/wiki:init` in any project. It will:
1. Create the `wiki/` and `.claude/wiki/` directories
2. Explore the project (structure, language, dependencies, architecture)
3. Ask you if something is unclear
4. Create knowledge articles for key concepts
5. Build the index

Safe to re-run — updates outdated articles without duplicating or deleting existing ones.

### Skill arguments

```bash
/wiki:init                             # first-time setup or update

/wiki:compile --all                    # force recompile everything
/wiki:compile --file daily/2026-04-12.md

/wiki:ingest --source design-specs     # one source group only
/wiki:ingest --dry-run --verbose       # preview

/wiki:query "How do I handle auth?"
/wiki:query "Auth patterns?" --file-back   # save answer as article

/wiki:lint --structural-only           # free checks only (no LLM)
```

## Hooks (automatic)

The plugin registers four hooks — no manual configuration needed:

| Hook | Event | Action |
|------|-------|--------|
| SessionStart | Session begins | Injects knowledge context (~60K chars) |
| SessionEnd | Session closes | Captures transcript, spawns flush |
| PreCompact | Before auto-compaction | Safety net — captures context before summarization |

## Data Layout

Knowledge base lives at project root (`wiki/`) and is meant to be committed. Operational state lives inside `.claude/wiki/` and is gitignored.

```
project/
├── wiki/                         # Knowledge base (committed)
│   ├── index.md                  # Article catalog (retrieval mechanism)
│   ├── compiled-truth.md         # Priority-scored dense summary
│   ├── log.md                    # Build log
│   ├── concepts/                 # Atomic knowledge articles
│   ├── connections/              # Cross-cutting insights
│   └── qa/                       # Filed query answers
├── .claude/
│   └── wiki/                     # Operational state (gitignored)
│       ├── daily/
│       │   └── YYYY-MM-DD.md     # Conversation logs (append-only)
│       ├── reports/              # Lint reports
│       ├── wip.md                # Work-in-progress resume state
│       ├── state.json            # Compilation tracking
│       └── last-flush.json       # Flush deduplication
```

## Source Ingestion

Create a `sources.yaml` in any project to ingest its documentation:

```yaml
version: 1

sources:
  - id: design-specs
    type: markdown
    include:
      - "docs/specs/*.md"
    category: design-specs
    description: "Project design specs"

  - id: external-articles
    type: markdown
    include:
      - "sources/articles/*.md"
    exclude:
      - "**/*DRAFT.md"
    category: external
    description: "Web clippings and research notes"
```

Then run `/wiki:ingest` from that project.

## Three-Level Retrieval

| Level | What | Size | Cost |
|-------|------|------|------|
| **Level 0: Map** | `index.md` — slug + one-line description | ~8K chars | Always injected |
| **Level 1: Truth** | `compiled-truth.md` — top articles by priority | ~40K chars | Always injected |
| **Level 2: Full** | Individual articles via `/wiki:query` or Read | On-demand | Per-query |

### Priority Scoring

`compile_truth.py` scores articles and fills a character budget (default 40K) from highest-scored down. Pinned articles (`pinned: true` in frontmatter) always go first.

| Signal | Weight | Measures |
|--------|--------|----------|
| Recency | 40% | Exponential decay from `updated` date |
| Linkedness | 35% | Log-scaled inbound `[[wikilinks]]` count |
| Access | 25% | Log-scaled `query.py` citation count |

## Cost

All operations use the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) on your existing Claude subscription. No separate API key needed.

| Operation | Cost | Frequency |
|-----------|------|-----------|
| Session flush | ~$0.01-0.05 | Every session end (auto) |
| Daily compilation | ~$0.30-0.80 | Once/day after 6 PM (auto) |
| Source ingestion | ~$0.30-0.80/file | Manual |
| Compiled truth | **$0.00** | After every compile/ingest |
| Structural lint | **$0.00** | Manual |
| Full lint | ~$0.15-0.25 | Manual |
| Query | ~$0.15-0.40 | Manual |

**Daily estimate** (10-15 sessions): **$0.40-1.10/day**

Costs stay constant as the knowledge base grows — the prompt includes an index and compiled truth (fixed size), not all articles.

## Why No RAG?

At personal scale (50-500 articles), the LLM reading a structured index outperforms vector similarity. The LLM understands what you're really asking; cosine similarity just finds similar words. RAG becomes useful at ~2,000+ articles when the index exceeds the context window.

## Obsidian Integration

The knowledge base is pure markdown with `[[wikilinks]]`. Point an Obsidian vault at your data directory's `knowledge/` folder for graph view, backlinks, and full-text search.

## Development

To test changes locally:

```bash
claude --plugin-dir .
/reload-plugins        # after edits
```

Check the `/plugin` Errors tab for any loading issues.

## Technical Reference

See [AGENTS.md](AGENTS.md) for the complete article schema, hook architecture, and customization options.

## Credits

- Forked from [coleam00/claude-memory-compiler](https://github.com/coleam00/claude-memory-compiler) by Cole Medin
- Inspired by [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- Built on the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) by Anthropic
