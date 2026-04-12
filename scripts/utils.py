"""Shared utilities for the personal knowledge base."""

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from config import (
    CONCEPTS_DIR,
    CONNECTIONS_DIR,
    DAILY_DIR,
    INDEX_FILE,
    KNOWLEDGE_DIR,
    LOG_FILE,
    QA_DIR,
    SOURCES_FILE,
    STATE_FILE,
)


# ── State management ──────────────────────────────────────────────────

def load_state() -> dict:
    """Load persistent state from state.json."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {
        "ingested_daily": {},
        "ingested_sources": {},
        "access_counts": {},
        "query_count": 0,
        "last_lint": None,
        "total_cost": 0.0,
    }


def save_state(state: dict) -> None:
    """Save state to state.json."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ── File hashing ──────────────────────────────────────────────────────

def file_hash(path: Path) -> str:
    """SHA-256 hash of a file (first 16 hex chars)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


# ── Slug / naming ─────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


# ── Source config ─────────────────────────────────────────────────────

@dataclass
class SourceGroup:
    """One entry from sources.yaml."""

    id: str
    type: str
    include: list[str]
    exclude: list[str] = field(default_factory=list)
    category: str = ""
    description: str = ""


def load_sources_config() -> list[SourceGroup]:
    """Read and validate sources.yaml. Returns empty list if file missing."""
    if not SOURCES_FILE.exists():
        return []

    import yaml

    raw = yaml.safe_load(SOURCES_FILE.read_text(encoding="utf-8"))
    if not raw or not isinstance(raw, dict):
        return []

    version = raw.get("version", 1)
    if version != 1:
        raise ValueError(f"Unsupported sources.yaml version: {version}")

    groups = []
    for entry in raw.get("sources", []):
        if not entry.get("id") or not entry.get("type") or not entry.get("include"):
            continue
        groups.append(SourceGroup(
            id=entry["id"],
            type=entry["type"],
            include=entry["include"],
            exclude=entry.get("exclude", []),
            category=entry.get("category", ""),
            description=entry.get("description", ""),
        ))
    return groups


def resolve_source_files(group: SourceGroup, root: Path | None = None) -> list[Path]:
    """Expand include globs and subtract exclude globs. Returns sorted unique paths."""
    import fnmatch

    base = root or Path.cwd()
    included: set[Path] = set()
    for pattern in group.include:
        for match in base.glob(pattern):
            if match.is_file():
                included.add(match.resolve())

    # Exclude patterns are matched against filenames (not re-globbed from root)
    # because include paths often escape the base dir via ../../ and re-globbing
    # from root wouldn't find those files.
    if group.exclude:
        filtered: set[Path] = set()
        for fpath in included:
            skip = False
            for pattern in group.exclude:
                # Strip leading **/ for fnmatch against filename
                pat = pattern.lstrip("*").lstrip("/")
                if fnmatch.fnmatch(fpath.name, pat):
                    skip = True
                    break
            if not skip:
                filtered.add(fpath)
        included = filtered

    return sorted(included)


def migrate_state_schema(state: dict) -> dict:
    """Migrate state.json from old schema (flat 'ingested') to new split schema.

    Old: {"ingested": {"2026-04-09.md": {...}}, ...}
    New: {"ingested_daily": {"2026-04-09.md": {...}}, "ingested_sources": {}, ...}

    Idempotent: safe to call multiple times.
    """
    if "ingested_daily" in state:
        state.setdefault("ingested_sources", {})
        return state

    if "ingested" in state:
        state["ingested_daily"] = state.pop("ingested")
    else:
        state["ingested_daily"] = {}

    state.setdefault("ingested_sources", {})
    return state


# ── Wikilink helpers ──────────────────────────────────────────────────

def extract_wikilinks(content: str) -> list[str]:
    """Extract all [[wikilinks]] from markdown content."""
    return re.findall(r"\[\[([^\]]+)\]\]", content)


def wiki_article_exists(link: str) -> bool:
    """Check if a wikilinked article exists on disk."""
    path = KNOWLEDGE_DIR / f"{link}.md"
    return path.exists()


# ── Wiki content helpers ──────────────────────────────────────────────

def read_wiki_index() -> str:
    """Read the knowledge base index file."""
    if INDEX_FILE.exists():
        return INDEX_FILE.read_text(encoding="utf-8")
    return "# Knowledge Base Index\n\n| Article | Summary | Compiled From | Updated |\n|---------|---------|---------------|---------|"


def read_all_wiki_content() -> str:
    """Read index + all wiki articles into a single string for context."""
    parts = [f"## INDEX\n\n{read_wiki_index()}"]

    for subdir in [CONCEPTS_DIR, CONNECTIONS_DIR, QA_DIR]:
        if not subdir.exists():
            continue
        for md_file in sorted(subdir.glob("*.md")):
            rel = md_file.relative_to(KNOWLEDGE_DIR)
            content = md_file.read_text(encoding="utf-8")
            parts.append(f"## {rel}\n\n{content}")

    return "\n\n---\n\n".join(parts)


def list_wiki_articles() -> list[Path]:
    """List all wiki article files."""
    articles = []
    for subdir in [CONCEPTS_DIR, CONNECTIONS_DIR, QA_DIR]:
        if subdir.exists():
            articles.extend(sorted(subdir.glob("*.md")))
    return articles


def list_raw_files() -> list[Path]:
    """List all daily log files."""
    if not DAILY_DIR.exists():
        return []
    return sorted(DAILY_DIR.glob("*.md"))


# ── Index helpers ─────────────────────────────────────────────────────

def count_inbound_links(target: str, exclude_file: Path | None = None) -> int:
    """Count how many wiki articles link to a given target."""
    count = 0
    for article in list_wiki_articles():
        if article == exclude_file:
            continue
        content = article.read_text(encoding="utf-8")
        if f"[[{target}]]" in content:
            count += 1
    return count


def get_article_word_count(path: Path) -> int:
    """Count words in an article, excluding YAML frontmatter."""
    content = path.read_text(encoding="utf-8")
    # Strip frontmatter
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3:]
    return len(content.split())


def build_index_entry(rel_path: str, summary: str, sources: str, updated: str) -> str:
    """Build a single index table row."""
    link = rel_path.replace(".md", "")
    return f"| [[{link}]] | {summary} | {sources} | {updated} |"
