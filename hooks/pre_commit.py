"""
PreToolUse hook - flushes conversation context before git commit.

Triggers on Bash tool calls that contain "git commit", ensuring the daily log
is up-to-date before code changes are committed. Since PreToolUse doesn't
receive transcript_path, the transcript is located via session_id.

The hook itself does NO API calls - only local file I/O for speed (<10s).
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path

# Recursion guard
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

# Ensure hooks/ is on sys.path for _shared import
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared import (
    _STATE_DIR,
    extract_conversation_context,
    find_transcript,
    parse_hook_stdin,
    spawn_flush,
)

MIN_TURNS_TO_FLUSH = 3

logging.basicConfig(
    filename=str(_STATE_DIR / "flush.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [pre-commit] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Match "git commit" but not "git commit --amend" (amend is typically trivial)
# and not comments or echo strings containing "git commit"
_GIT_COMMIT_RE = re.compile(r"(?:^|&&|\|\||;)\s*git\s+commit\b")


def main() -> None:
    try:
        hook_input = parse_hook_stdin()
    except (json.JSONDecodeError, ValueError, EOFError) as e:
        logging.error("Failed to parse stdin: %s", e)
        return

    session_id = hook_input.get("session_id", "unknown")
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Only intercept Bash tool calls
    if tool_name != "Bash":
        return

    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not _GIT_COMMIT_RE.search(command):
        return

    logging.info("Pre-commit flush triggered: session=%s cmd=%s", session_id, command[:80])

    # PreToolUse doesn't provide transcript_path — find it by session_id
    transcript_path = find_transcript(session_id)
    if not transcript_path:
        logging.info("SKIP: transcript not found for session %s", session_id)
        return

    try:
        context, turn_count = extract_conversation_context(transcript_path)
    except Exception as e:
        logging.error("Context extraction failed: %s", e)
        return

    if turn_count < MIN_TURNS_TO_FLUSH:
        logging.info("SKIP: only %d turns (min %d)", turn_count, MIN_TURNS_TO_FLUSH)
        return

    spawn_flush(context, session_id, log_prefix="pre-commit")


if __name__ == "__main__":
    main()
