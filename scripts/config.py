"""Path constants and configuration for the wiki plugin.

All data paths resolve from WIKI_DATA_DIR env var (set by bin/wiki-run from
userConfig). Falls back to ./data/ for local development without the plugin.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

# ── Plugin paths ──────────────────────────────────────────────────────
_PLUGIN_ROOT = Path(
    os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent))
)
_DATA_DIR = Path(os.environ.get("WIKI_DATA_DIR", str(Path.cwd() / "wiki")))

# ── Data directories (user-configurable location) ────────────────────
KNOWLEDGE_DIR = _DATA_DIR / "knowledge"
DAILY_DIR = _DATA_DIR / "daily"
CONCEPTS_DIR = KNOWLEDGE_DIR / "concepts"
CONNECTIONS_DIR = KNOWLEDGE_DIR / "connections"
QA_DIR = KNOWLEDGE_DIR / "qa"
REPORTS_DIR = _DATA_DIR / "reports"

WIP_FILE = _DATA_DIR / "wip.md"
INDEX_FILE = KNOWLEDGE_DIR / "index.md"
LOG_FILE = KNOWLEDGE_DIR / "log.md"
STATE_FILE = _DATA_DIR / "state.json"
FLUSH_STATE_FILE = _DATA_DIR / "last-flush.json"

# ── Plugin root (read-only, ships with plugin) ───────────────────────
SCRIPTS_DIR = _PLUGIN_ROOT / "scripts"
HOOKS_DIR = _PLUGIN_ROOT / "hooks"
AGENTS_FILE = _PLUGIN_ROOT / "AGENTS.md"

# ── Per-project config ───────────────────────────────────────────────
SOURCES_FILE = Path.cwd() / "sources.yaml"

# ── Timezone ─────────────────────────────────────────────────────────
TIMEZONE = os.environ.get("CLAUDE_PLUGIN_OPTION_TIMEZONE", "America/Chicago")


def now_iso() -> str:
    """Current time in ISO 8601 format."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    """Current date in ISO 8601 format."""
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
