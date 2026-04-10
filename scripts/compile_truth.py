"""
Generate compiled-truth.md from all wiki articles.

Extracts the Truth section (or fallback Key Points) from every concept and
connection article, concatenates them alphabetically, and writes a single
compiled-truth.md file. Zero LLM cost — pure file I/O.

Usage:
    uv run python scripts/compile_truth.py
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from config import KNOWLEDGE_DIR, CONCEPTS_DIR, CONNECTIONS_DIR, QA_DIR


COMPILED_TRUTH_FILE = KNOWLEDGE_DIR / "compiled-truth.md"


def strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter (--- delimited) from article content."""
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            return content[end + 3:].strip()
    return content.strip()


def extract_truth_section(content: str) -> str | None:
    """Extract the ## Truth section from a new-format article.

    Returns everything between '## Truth' and the next '---' horizontal rule
    or '## Timeline' header, whichever comes first. Returns None if no
    ## Truth header found.
    """
    match = re.search(r"^## Truth\s*\n", content, re.MULTILINE)
    if not match:
        return None

    start = match.end()
    boundary = re.search(r"^(?:---|\#\# Timeline)\s*$", content[start:], re.MULTILINE)
    if boundary:
        truth = content[start:start + boundary.start()]
    else:
        truth = content[start:]

    return truth.strip()


def extract_fallback_truth(content: str) -> str:
    """Extract truth from old-format articles (no ## Truth header).

    Fallback strategy:
    1. Intro paragraph (text before first ## heading)
    2. ## Key Points section
    3. ## Related Concepts section
    If no Key Points, use first 200 words of ## Details instead.
    """
    body = strip_frontmatter(content)

    parts: list[str] = []

    # 1. Intro paragraph — everything before the first ## heading
    lines = body.split("\n")
    intro_lines: list[str] = []
    for line in lines:
        if line.startswith("# ") and not intro_lines:
            continue  # skip title
        if line.startswith("## "):
            break
        intro_lines.append(line)
    intro = "\n".join(intro_lines).strip()
    if intro:
        parts.append(intro)

    # 2. Key Points section
    key_points = extract_section(body, "Key Points")
    if key_points:
        parts.append(f"### Key Points\n\n{key_points}")
    else:
        details = extract_section(body, "Details")
        if details:
            words = details.split()
            truncated = " ".join(words[:200])
            if len(words) > 200:
                truncated += "..."
            parts.append(f"### Details (excerpt)\n\n{truncated}")

    # 3. Related Concepts (look for both ## and ### levels)
    related = extract_section(body, "Related Concepts")
    if related:
        parts.append(f"### Related Concepts\n\n{related}")

    return "\n\n".join(parts)


def extract_section(body: str, heading: str) -> str | None:
    """Extract content under a ## or ### heading, up to the next same-or-higher heading."""
    pattern = rf"^#{2,3}\s+{re.escape(heading)}\s*\n"
    match = re.search(pattern, body, re.MULTILINE)
    if not match:
        return None

    start = match.end()
    level = match.group().count("#")

    next_heading = re.search(
        rf"^#{{{1},{level}}}\s+\S",
        body[start:],
        re.MULTILINE,
    )
    if next_heading:
        section = body[start:start + next_heading.start()]
    else:
        section = body[start:]

    return section.strip() or None


def compile_truth() -> tuple[int, int]:
    """Generate compiled-truth.md. Returns (article_count, new_format_count)."""
    articles: list[tuple[str, str]] = []
    new_format_count = 0

    for subdir in [CONCEPTS_DIR, CONNECTIONS_DIR]:
        if not subdir.exists():
            continue
        for md_file in sorted(subdir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            rel = md_file.relative_to(KNOWLEDGE_DIR)

            truth = extract_truth_section(content)
            if truth:
                new_format_count += 1
            else:
                truth = extract_fallback_truth(content)

            if truth:
                articles.append((str(rel).replace("\\", "/"), truth))

    now = datetime.now(timezone.utc).astimezone()
    timestamp = now.isoformat(timespec="seconds")

    lines = [
        "# Compiled Truth",
        "",
        f"> {len(articles)} articles | Generated {timestamp}",
    ]

    for rel_path, truth in articles:
        slug = rel_path.replace(".md", "")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(f"## {slug}")
        lines.append("")
        lines.append(truth)

    lines.append("")

    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    COMPILED_TRUTH_FILE.write_text("\n".join(lines), encoding="utf-8")

    return len(articles), new_format_count


def main():
    article_count, new_count = compile_truth()
    old_count = article_count - new_count
    print(f"Compiled truth: {article_count} articles ({new_count} new format, {old_count} legacy)")
    print(f"Written to: {COMPILED_TRUTH_FILE}")


if __name__ == "__main__":
    main()
