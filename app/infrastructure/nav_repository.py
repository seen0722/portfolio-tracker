"""Persisted daily NAV series (SQLite) — the real history that replaces the
old simulated-history hack. Stored in the same DB file as the ledger via its
own short-lived connection.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union

import pandas as pd

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nav_points (
    date      TEXT PRIMARY KEY,
    total_usd REAL NOT NULL,
    total_twd REAL NOT NULL
);
"""

_COLUMNS = ["date", "total_usd", "total_twd", "daily_return_pct"]


class NavRepository:
    """Store and load daily portfolio NAV snapshots."""

    def __init__(self, db_path: Union[str, Path] = "portfolio.db") -> None:
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def upsert(self, record_date: str, total_usd: float, total_twd: float) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO nav_points (date, total_usd, total_twd) VALUES (?, ?, ?)",
            (record_date, round(total_usd, 2), round(total_twd, 2)),
        )
        self._conn.commit()

    def replace_all(self, df: pd.DataFrame) -> None:
        """Replace the whole series (used by reconstruction)."""
        self._conn.execute("DELETE FROM nav_points")
        rows = [
            (str(r["date"]), float(r["total_usd"]), float(r["total_twd"]))
            for _, r in df.iterrows()
        ]
        self._conn.executemany(
            "INSERT OR REPLACE INTO nav_points (date, total_usd, total_twd) VALUES (?, ?, ?)",
            rows,
        )
        self._conn.commit()

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) AS n FROM nav_points").fetchone()["n"])

    def load(self) -> pd.DataFrame:
        """Return the series sorted by date with daily_return_pct recomputed."""
        rows = self._conn.execute(
            "SELECT date, total_usd, total_twd FROM nav_points ORDER BY date"
        ).fetchall()
        if not rows:
            return pd.DataFrame(columns=_COLUMNS)
        df = pd.DataFrame([dict(r) for r in rows])
        df["daily_return_pct"] = df["total_usd"].pct_change().fillna(0.0) * 100.0
        return df

    def close(self) -> None:
        self._conn.close()
