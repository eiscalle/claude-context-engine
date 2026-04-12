"""Path constants and configuration for the wiki plugin.

Knowledge base (wiki/) lives at project root and is meant to be committed.
Operational state (daily logs, flush state, etc.) lives in .claude/wiki/
and is typically gitignored.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

# ── Plugin paths ──────────────────────────────────────────────────────
_PLUGIN_ROOT = Path(
    os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent))
)
_PROJECT_ROOT = Path(os.environ.get("WIKI_PROJECT_ROOT", str(Path.cwd())))

# ── Knowledge base (committed) ───────────────────────────────────────
KNOWLEDGE_DIR = _PROJECT_ROOT / "wiki"
CONCEPTS_DIR = KNOWLEDGE_DIR / "concepts"
CONNECTIONS_DIR = KNOWLEDGE_DIR / "connections"
QA_DIR = KNOWLEDGE_DIR / "qa"
INDEX_FILE = KNOWLEDGE_DIR / "index.md"
LOG_FILE = KNOWLEDGE_DIR / "log.md"

# ── Operational state (gitignored, inside .claude/) ──────────────────
_STATE_DIR = _PROJECT_ROOT / ".claude" / "wiki"
DAILY_DIR = _STATE_DIR / "daily"
REPORTS_DIR = _STATE_DIR / "reports"
WIP_FILE = _STATE_DIR / "wip.md"
STATE_FILE = _STATE_DIR / "state.json"
FLUSH_STATE_FILE = _STATE_DIR / "last-flush.json"

# ── Plugin root (read-only, ships with plugin) ───────────────────────
SCRIPTS_DIR = _PLUGIN_ROOT / "scripts"
HOOKS_DIR = _PLUGIN_ROOT / "hooks"
AGENTS_FILE = _PLUGIN_ROOT / "AGENTS.md"

# ── Per-project config ───────────────────────────────────────────────
SOURCES_FILE = _PROJECT_ROOT / "sources.yaml"

# ── Timezone ─────────────────────────────────────────────────────────
TIMEZONE = os.environ.get("CLAUDE_PLUGIN_OPTION_TIMEZONE", "America/Chicago")


def now_iso() -> str:
    """Current time in ISO 8601 format."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    """Current date in ISO 8601 format."""
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
