"""Command-line interface: `quotapulse record | collect | status | history`."""
from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Optional, Sequence

from quotapulse import claude_usage
from quotapulse.pace import Forecast, forecast
from quotapulse.store import Snapshot, Store, default_db_path

STALE_AFTER_S = 15 * 60
BAR_WIDTH = 20
SPARK_BLOCKS = "▁▂▃▄▅▆▇█"


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    store = Store(default_db_path())
    try:
        return args.func(store, args)
    finally:
        store.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quotapulse",
        description="Track AI usage quotas locally and forecast when you'll hit a limit.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record", help="record a reading copied from an app's usage page")
    record.add_argument("account", help="name for this account, e.g. codex or cursor")
    record.add_argument("--used-pct", type=_percent, required=True, help="percent of the limit used, 0-100")
    record.add_argument("--resets-in-minutes", type=float, help="minutes until this limit resets")
    record.set_defaults(func=cmd_record)

    collect = sub.add_parser("collect", help="sum Claude Code token usage in the last 5 hours")
    collect.add_argument("--account", default="claude", help="account name to store under")
    collect.add_argument("--budget-tokens", type=int, help="your 5-hour token allowance; enables a percentage")
    collect.add_argument("--projects-dir", type=Path, help="transcript folder (default: ~/.claude/projects)")
    collect.set_defaults(func=cmd_collect)

    status = sub.add_parser("status", help="show the latest reading and pace for every account")
    status.add_argument("--threshold", type=_percent, default=80.0, help="limit to forecast against (default 80)")
    status.set_defaults(func=cmd_status)

    history = sub.add_parser("history", help="show a sparkline of recent usage for one account")
    history.add_argument("account")
    history.add_argument("--hours", type=float, default=6.0)
    history.set_defaults(func=cmd_history)

    return parser


def cmd_record(store: Store, args: argparse.Namespace) -> int:
    now = time.time()
    resets_at = now + args.resets_in_minutes * 60 if args.resets_in_minutes is not None else None
    store.add(Snapshot(account=args.account, ts=now, source="manual", used_pct=args.used_pct, resets_at=resets_at))
    print(f"Recorded {args.account}: {args.used_pct:.1f}% used")
    return 0


def cmd_collect(store: Store, args: argparse.Namespace) -> int:
    now = time.time()
    projects_dir = args.projects_dir or claude_usage.default_projects_dir()
    totals = claude_usage.window_totals(projects_dir, now)

    used_pct = None
    if args.budget_tokens:
        used_pct = min(100.0, totals.total / args.budget_tokens * 100.0)

    store.add(Snapshot(account=args.account, ts=now, source="claude_transcripts", used_pct=used_pct, tokens=totals.total))
    if used_pct is None:
        print(f"{args.account}: {totals.total:,} tokens in the last 5h (no --budget-tokens, so no percentage)")
    else:
        print(f"{args.account}: {totals.total:,} tokens in the last 5h ({used_pct:.1f}% of budget)")
    return 0


def cmd_status(store: Store, args: argparse.Namespace) -> int:
    accounts = store.accounts()
    if not accounts:
        print("No data yet. Try `quotapulse collect` or `quotapulse record <account> --used-pct N`.")
        return 0

    now = time.time()
    print(f"{'ACCOUNT':<14}{'USED':>6}  {'':<{BAR_WIDTH}}  {'RESETS':>8}  PACE")
    for account in accounts:
        latest = store.latest(account)
        if latest is None:
            continue
        points = [
            (s.ts, s.used_pct)
            for s in store.history(account, since=now - 2 * 3600)
            if s.used_pct is not None
        ]
        fc = forecast(points, args.threshold, now) if points else Forecast(None, None)

        used = f"{latest.used_pct:.0f}%" if latest.used_pct is not None else "-"
        bar = _bar(latest.used_pct) if latest.used_pct is not None else " " * BAR_WIDTH
        resets = format_duration(latest.resets_at - now) if latest.resets_at else "-"
        stale = "  (stale)" if now - latest.ts > STALE_AFTER_S else ""
        print(f"{account:<14}{used:>6}  {bar}  {resets:>8}  {_pace_text(fc, args.threshold, now)}{stale}")
    return 0


def cmd_history(store: Store, args: argparse.Namespace) -> int:
    now = time.time()
    rows = [s for s in store.history(args.account, since=now - args.hours * 3600) if s.used_pct is not None]
    if not rows:
        print(f"No usage percentages for {args.account} in the last {args.hours:g}h.")
        return 1

    values = [s.used_pct for s in rows]
    print(f"{args.account}, last {args.hours:g}h ({len(values)} samples)")
    print(sparkline(values, width=60))
    print(f"min {min(values):.1f}%   max {max(values):.1f}%   now {values[-1]:.1f}%")
    return 0


def sparkline(values: Sequence[float], width: int) -> str:
    """Bucket values into `width` columns, each showing its peak, on a fixed 0-100 scale."""
    width = max(1, min(width, len(values)))
    cells = []
    for i in range(width):
        lo = i * len(values) // width
        hi = max(lo + 1, (i + 1) * len(values) // width)
        peak = max(values[lo:hi])
        cells.append(SPARK_BLOCKS[min(len(SPARK_BLOCKS) - 1, int(peak / 100.0 * len(SPARK_BLOCKS)))])
    return "".join(cells)


def format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "now"
    minutes = int(seconds // 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def _pace_text(fc: Forecast, threshold: float, now: float) -> str:
    if fc.rate_pct_per_hour is None:
        return "not enough data yet"
    if fc.rate_pct_per_hour <= 0:
        return "flat"
    rate = f"+{fc.rate_pct_per_hour:.1f}%/h"
    if fc.reaches_threshold_at is None:
        return rate
    if fc.reaches_threshold_at <= now:
        return f"{rate}, past {threshold:.0f}% already"
    return f"{rate}, hits {threshold:.0f}% in {format_duration(fc.reaches_threshold_at - now)}"


def _bar(pct: float) -> str:
    filled = round(max(0.0, min(100.0, pct)) / 100.0 * BAR_WIDTH)
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def _percent(text: str) -> float:
    value = float(text)
    if not 0.0 <= value <= 100.0:
        raise argparse.ArgumentTypeError("must be between 0 and 100")
    return value
