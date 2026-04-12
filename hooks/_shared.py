"""
Shared logic for Claude Code hooks that extract conversation context and spawn flush.py.

Used by: session_end.py, pre_compact.py, pre_commit.py
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_PLUGIN_ROOT = Path(
    os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent))
)
_STATE_DIR = Path.cwd() / ".claude" / "wiki"

SCRIPTS_DIR = _PLUGIN_ROOT / "scripts"

MAX_TURNS = 30
MAX_CONTEXT_CHARS = 15_000


def parse_hook_stdin() -> dict:
    """Read and parse JSON from stdin (Claude Code hook input).

    Handles Windows paths with unescaped backslashes.
    Returns parsed dict or raises on failure.
    """
    raw = sys.stdin.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        fixed = re.sub(r'(?<!\\)\\(?!["\\])', r'\\\\', raw)
        return json.loads(fixed)


def extract_conversation_context(transcript_path: Path) -> tuple[str, int]:
    """Read JSONL transcript and extract last ~N conversation turns as markdown."""
    turns: list[str] = []

    with open(transcript_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg = entry.get("message", {})
            if isinstance(msg, dict):
                role = msg.get("role", "")
                content = msg.get("content", "")
            else:
                role = entry.get("role", "")
                content = entry.get("content", "")

            if role not in ("user", "assistant"):
                continue

            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        text_parts.append(block)
                content = "\n".join(text_parts)

            if isinstance(content, str) and content.strip():
                label = "User" if role == "user" else "Assistant"
                turns.append(f"**{label}:** {content.strip()}\n")

    recent = turns[-MAX_TURNS:]
    context = "\n".join(recent)

    if len(context) > MAX_CONTEXT_CHARS:
        context = context[-MAX_CONTEXT_CHARS:]
        boundary = context.find("\n**")
        if boundary > 0:
            context = context[boundary + 1:]

    return context, len(recent)


def spawn_flush(context: str, session_id: str, *, log_prefix: str = "hook") -> bool:
    """Write context to temp file and spawn flush.py in background.

    Returns True if flush was spawned, False on skip/error.
    """
    if not context.strip():
        logging.info("SKIP: empty context")
        return False

    # Write context file to data dir (writable)
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
    context_file = _STATE_DIR / f"flush-context-{session_id}-{timestamp}.md"
    context_file.write_text(context, encoding="utf-8")

    flush_script = SCRIPTS_DIR / "flush.py"
    wiki_run = str(_PLUGIN_ROOT / "bin" / "wiki-run")
    cmd = [wiki_run, str(flush_script), str(context_file), session_id]

    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )
        logging.info("[%s] Spawned flush.py for session %s (%d chars)",
                     log_prefix, session_id, len(context))
        return True
    except Exception as e:
        logging.error("[%s] Failed to spawn flush.py: %s", log_prefix, e)
        return False


def find_transcript(session_id: str) -> Path | None:
    """Locate transcript JSONL by session_id in ~/.claude/projects/.

    Searches the project directory matching current working directory first,
    then falls back to a broad search.
    """
    claude_projects = Path.home() / ".claude" / "projects"
    if not claude_projects.exists():
        return None

    # Derive project slug from CWD (not plugin root)
    cwd_slug = str(Path.cwd()).replace("/", "-").replace("\\", "-")
    if not cwd_slug.startswith("-"):
        cwd_slug = "-" + cwd_slug

    # Try exact project directory first
    project_dir = claude_projects / cwd_slug
    if project_dir.exists():
        candidate = project_dir / f"{session_id}.jsonl"
        if candidate.exists():
            return candidate

    # Broad fallback: scan all project dirs
    for jsonl in claude_projects.rglob(f"{session_id}.jsonl"):
        if "subagents" not in jsonl.parts:
            return jsonl

    return None
