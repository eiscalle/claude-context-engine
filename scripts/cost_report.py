"""
Cost report for the context engine.

Reads state.json (compile/ingest costs) and last-flush.json (flush costs)
to produce a summary of spending by time period and operation type.

Usage:
    uv run python scripts/cost_report.py              # today
    uv run python scripts/cost_report.py --week        # last 7 days
    uv run python scripts/cost_report.py --month       # this month
    uv run python scripts/cost_report.py --all         # lifetime
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import STATE_FILE, FLUSH_STATE_FILE


def load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def parse_iso_timestamp(ts: str) -> float:
    """Convert ISO 8601 timestamp string to Unix epoch seconds."""
    try:
        return datetime.fromisoformat(ts).timestamp()
    except (ValueError, TypeError):
        return 0.0


def get_flush_costs(state: dict, since: float) -> list[dict]:
    """Filter flush_costs entries since a given timestamp."""
    return [
        e for e in state.get("flush_costs", [])
        if e.get("timestamp", 0) >= since
    ]


def get_compile_costs(state: dict, since: float) -> list[tuple[str, float]]:
    """Filter ingested_daily entries since a given timestamp."""
    results = []
    for name, entry in state.get("ingested_daily", {}).items():
        ts = parse_iso_timestamp(entry.get("compiled_at", ""))
        if ts >= since:
            results.append((name, entry.get("cost_usd", 0.0)))
    return results


def get_ingest_costs(state: dict, since: float) -> list[tuple[str, float]]:
    """Filter ingested_sources entries since a given timestamp."""
    results = []
    for name, entry in state.get("ingested_sources", {}).items():
        ts = parse_iso_timestamp(entry.get("ingested_at", ""))
        if ts >= since:
            results.append((name, entry.get("cost_usd", 0.0)))
    return results


def format_section(label: str, flush_costs: list, compile_costs: list, ingest_costs: list) -> str:
    flush_total = sum(e.get("cost_usd", 0.0) for e in flush_costs)
    compile_total = sum(c for _, c in compile_costs)
    ingest_total = sum(c for _, c in ingest_costs)
    grand_total = flush_total + compile_total + ingest_total
    total_ops = len(flush_costs) + len(compile_costs) + len(ingest_costs)

    lines = [
        f"{label}:",
        f"  Flushes:   {len(flush_costs):>4} calls   ${flush_total:>7.2f}",
        f"  Compile:   {len(compile_costs):>4} calls   ${compile_total:>7.2f}",
        f"  Ingest:    {len(ingest_costs):>4} calls   ${ingest_total:>7.2f}",
        f"  {'-' * 30}",
        f"  Total:     {total_ops:>4} calls   ${grand_total:>7.2f}",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Context engine cost report")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--week", action="store_true", help="Last 7 days")
    group.add_argument("--month", action="store_true", help="This month")
    group.add_argument("--all", action="store_true", help="Lifetime")
    args = parser.parse_args()

    state = load_json(STATE_FILE)
    flush_state = load_json(FLUSH_STATE_FILE)

    now = datetime.now(timezone.utc).astimezone()

    # Time boundaries
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    week_start = (now - timedelta(days=7)).timestamp()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()

    print(f"Cost Report: {now.strftime('%Y-%m-%d')}")
    print("-" * 40)

    if args.all:
        flushes = get_flush_costs(flush_state, 0)
        compiles = get_compile_costs(state, 0)
        ingests = get_ingest_costs(state, 0)
        print(format_section("Lifetime", flushes, compiles, ingests))
        grand = sum(e.get("cost_usd", 0) for e in flushes) + sum(c for _, c in compiles) + sum(c for _, c in ingests)
        print(f"\nTotal lifetime cost: ${grand:.2f}")
    elif args.month:
        flushes = get_flush_costs(flush_state, month_start)
        compiles = get_compile_costs(state, month_start)
        ingests = get_ingest_costs(state, month_start)
        print(format_section(f"This month ({now.strftime('%B %Y')})", flushes, compiles, ingests))
    elif args.week:
        flushes = get_flush_costs(flush_state, week_start)
        compiles = get_compile_costs(state, week_start)
        ingests = get_ingest_costs(state, week_start)
        print(format_section("Last 7 days", flushes, compiles, ingests))
    else:
        # Default: today + this month
        t_flushes = get_flush_costs(flush_state, today_start)
        t_compiles = get_compile_costs(state, today_start)
        t_ingests = get_ingest_costs(state, today_start)
        print(format_section("Today", t_flushes, t_compiles, t_ingests))

        print()

        m_flushes = get_flush_costs(flush_state, month_start)
        m_compiles = get_compile_costs(state, month_start)
        m_ingests = get_ingest_costs(state, month_start)
        print(format_section(f"This month ({now.strftime('%B %Y')})", m_flushes, m_compiles, m_ingests))

        lifetime_total = state.get("total_cost", 0.0)
        if lifetime_total > 0:
            print(f"\nLifetime total (from state.json): ${lifetime_total:.2f}")


if __name__ == "__main__":
    main()
