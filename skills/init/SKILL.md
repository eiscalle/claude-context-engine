---
description: Initialize or update the wiki knowledge base for this project. Creates required directories, explores the codebase, and populates the knowledge base with project context. Safe to run repeatedly — updates outdated info without losing existing articles.
---

# Wiki Init

You are initializing (or updating) the project's wiki knowledge base. Follow these steps carefully.

## Step 1: Create directories

Ensure the following directories exist (create if missing, skip if present):
- `wiki/` (knowledge base root)
- `wiki/concepts/`
- `wiki/connections/`
- `wiki/qa/`
- `.claude/wiki/` (operational state)
- `.claude/wiki/daily/`
- `.claude/wiki/reports/`

## Step 2: Explore the project

Thoroughly explore the current project to understand:
- **What it is**: language, framework, purpose, domain
- **Architecture**: key directories, entry points, main modules
- **Dependencies**: package manager, key libraries
- **Conventions**: naming, patterns, project structure
- **Configuration**: build system, CI/CD, environment setup
- **Key abstractions**: core types, interfaces, data models

Use Glob, Grep, and Read tools to explore. Read README, package.json/pyproject.toml/Cargo.toml, main entry points, and key source files. Don't read every file — focus on understanding the structure and key decisions.

If something is unclear or ambiguous (e.g., the purpose of an unusual directory, or a non-obvious architectural choice), **ask the user** rather than guessing.

## Step 3: Check existing knowledge base

Read `wiki/index.md` if it exists. Compare what's already documented against what you discovered:
- **New articles needed**: concepts not yet in the wiki
- **Updates needed**: existing articles with outdated information
- **No action needed**: articles that are still accurate

Do NOT create duplicates. Do NOT delete or overwrite articles that are still correct.

## Step 4: Write/update articles

For each concept worth documenting, create or update articles following this format:

### File: `wiki/concepts/<slug>.md`

```markdown
---
title: "<Title>"
aliases: [<alternate names>]
tags: [<relevant tags>]
sources:
  - "init-scan"
created: <today's date>
updated: <today's date>
---

## Truth

<2-4 sentence explanation of current facts. Dense, factual, no narrative.>

### Key Points
- <3-5 self-contained factual bullets>

### Related Concepts
- [[concepts/<related>]] — <one-line description>

---

## Timeline

### <today's date> | init-scan
- Initial documentation from project exploration
```

Create `wiki/connections/` articles for non-obvious relationships between concepts.

### Quality rules:
- Every article links to at least 2 other articles via `[[wikilinks]]`
- Key Points: 3-5 bullets
- Truth section: facts only, encyclopedia style
- One concept per article — split if a topic is too broad

## Step 5: Update index

Create or update `wiki/index.md` with a table of all articles:

```markdown
# Knowledge Base Index

| Article | Summary | Source | Updated |
|---------|---------|--------|---------|
| [[concepts/slug]] | One-line summary | init-scan | <date> |
```

## Step 6: Report

Tell the user what you did:
- How many articles created vs updated vs unchanged
- Key concepts documented
- Anything you couldn't figure out (suggest the user clarify in a follow-up)
