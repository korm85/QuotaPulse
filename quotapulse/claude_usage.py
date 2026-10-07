"""Token usage from local Claude Code transcripts (JSONL files)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

WINDOW_SECONDS = 5 * 3600


@dataclass(frozen=True)
class TokenTotals:
    input: int = 0
    output: int = 0
    cache_creation: int = 0
    cache_read: int = 0

    @property
    def total(self) -> int:
        return self.input + self.output + self.cache_creation + self.cache_read


def default_projects_dir() -> Path:
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(config_dir) if config_dir else Path.home() / ".claude"
    return base / "projects"


def window_totals(projects_dir: Path, now: float, window_s: float = WINDOW_SECONDS) -> TokenTotals:
    """Sum token usage from transcript entries newer than `now - window_s`."""
    if not projects_dir.exists():
        return TokenTotals()

    cutoff = now - window_s
    counts = {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0}
    seen_message_ids: set[str] = set()

    for path in projects_dir.rglob("*.jsonl"):
        try:
            if path.stat().st_mtime < cutoff:
                continue
            with path.open(encoding="utf-8", errors="ignore") as f:
                for line in f:
                    _add_entry(line, cutoff, counts, seen_message_ids)
        except OSError:
            continue

    return TokenTotals(**counts)


def _add_entry(line: str, cutoff: float, counts: dict, seen_message_ids: set) -> None:
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        return
    if not isinstance(entry, dict):
        return

    ts = _epoch(entry.get("timestamp"))
    if ts is None or ts < cutoff:
        return

    message = entry.get("message")
    usage = message.get("usage") if isinstance(message, dict) else None
    if not isinstance(usage, dict):
        return

    # A streamed reply can be logged on several lines that repeat the same usage.
    message_id = message.get("id")
    if message_id:
        if message_id in seen_message_ids:
            return
        seen_message_ids.add(message_id)

    counts["input"] += int(usage.get("input_tokens") or 0)
    counts["output"] += int(usage.get("output_tokens") or 0)
    counts["cache_creation"] += int(usage.get("cache_creation_input_tokens") or 0)
    counts["cache_read"] += int(usage.get("cache_read_input_tokens") or 0)


def _epoch(value: object) -> Optional[float]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None
