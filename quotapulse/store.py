"""Local SQLite history of quota snapshots."""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def default_db_path() -> Path:
    override = os.environ.get("QUOTAPULSE_DB")
    if override:
        return Path(override)
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return data_home / "quotapulse" / "quotapulse.db"


@dataclass(frozen=True)
class Snapshot:
    account: str
    ts: float
    source: str
    used_pct: Optional[float] = None
    tokens: Optional[int] = None
    resets_at: Optional[float] = None


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS snapshots (
                account TEXT NOT NULL,
                ts REAL NOT NULL,
                source TEXT NOT NULL,
                used_pct REAL,
                tokens INTEGER,
                resets_at REAL,
                PRIMARY KEY (account, ts)
            )"""
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def add(self, snap: Snapshot) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO snapshots VALUES (?, ?, ?, ?, ?, ?)",
            (snap.account, snap.ts, snap.source, snap.used_pct, snap.tokens, snap.resets_at),
        )
        self.conn.commit()

    def accounts(self) -> list[str]:
        rows = self.conn.execute("SELECT DISTINCT account FROM snapshots ORDER BY account")
        return [row["account"] for row in rows.fetchall()]

    def latest(self, account: str) -> Optional[Snapshot]:
        row = self.conn.execute(
            "SELECT * FROM snapshots WHERE account = ? ORDER BY ts DESC LIMIT 1", (account,)
        ).fetchone()
        return _to_snapshot(row) if row else None

    def history(self, account: str, since: float) -> list[Snapshot]:
        rows = self.conn.execute(
            "SELECT * FROM snapshots WHERE account = ? AND ts >= ? ORDER BY ts", (account, since)
        ).fetchall()
        return [_to_snapshot(row) for row in rows]


def _to_snapshot(row: sqlite3.Row) -> Snapshot:
    return Snapshot(
        account=row["account"],
        ts=row["ts"],
        source=row["source"],
        used_pct=row["used_pct"],
        tokens=row["tokens"],
        resets_at=row["resets_at"],
    )
