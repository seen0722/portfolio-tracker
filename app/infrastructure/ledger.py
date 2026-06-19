"""SQLite-backed transaction ledger (stdlib sqlite3, no ORM ceremony).

This is the system of record, replacing portfolio.json. A single writer (the web
app + scheduled jobs that serialize) makes SQLite ideal: ACID, zero-ops,
single-file backup. SQLAlchemy/Alembic can be introduced later if migrations
ever get painful; the LedgerRepository Protocol keeps that swap cheap.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import List, Union

from app.domain.transactions import Transaction, TxnType

_SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_type       TEXT    NOT NULL,
    symbol         TEXT    NOT NULL,
    trade_date     TEXT    NOT NULL,
    quantity       REAL    NOT NULL DEFAULT 0,
    price          REAL    NOT NULL DEFAULT 0,
    fee            REAL    NOT NULL DEFAULT 0,
    currency       TEXT    NOT NULL DEFAULT 'USD',
    account        TEXT    NOT NULL DEFAULT 'default',
    ratio          REAL    NOT NULL DEFAULT 0,
    related_symbol TEXT    NOT NULL DEFAULT '',
    note           TEXT    NOT NULL DEFAULT '',
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_txn_symbol ON transactions(symbol);
CREATE INDEX IF NOT EXISTS idx_txn_date   ON transactions(trade_date);
"""

_INSERT = """
INSERT INTO transactions
    (txn_type, symbol, trade_date, quantity, price, fee,
     currency, account, ratio, related_symbol, note)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


class SqliteLedger:
    """Concrete LedgerRepository on top of stdlib sqlite3."""

    def __init__(self, db_path: Union[str, Path] = "portfolio.db") -> None:
        self.db_path = str(db_path)
        # check_same_thread=False: Flask request threads + APScheduler jobs share
        # this connection; writes are short and serialized by SQLite's lock.
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def add(self, txn: Transaction) -> Transaction:
        cur = self._conn.execute(
            _INSERT,
            (
                txn.txn_type.value,
                txn.symbol,
                txn.trade_date.isoformat(),
                txn.quantity,
                txn.price,
                txn.fee,
                txn.currency,
                txn.account,
                txn.ratio,
                txn.related_symbol,
                txn.note,
            ),
        )
        self._conn.commit()
        return replace(txn, id=cur.lastrowid)

    def add_many(self, txns: List[Transaction]) -> List[Transaction]:
        return [self.add(txn) for txn in txns]

    def all(self) -> List[Transaction]:
        rows = self._conn.execute(
            "SELECT * FROM transactions ORDER BY trade_date, id"
        ).fetchall()
        return [self._row_to_txn(row) for row in rows]

    def by_symbol(self, symbol: str) -> List[Transaction]:
        rows = self._conn.execute(
            "SELECT * FROM transactions WHERE symbol = ? ORDER BY trade_date, id",
            (symbol,),
        ).fetchall()
        return [self._row_to_txn(row) for row in rows]

    def symbols(self) -> List[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT symbol FROM transactions ORDER BY symbol"
        ).fetchall()
        return [row["symbol"] for row in rows]

    def delete(self, txn_id: int) -> None:
        self._conn.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
        self._conn.commit()

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM transactions").fetchone()
        return int(row["n"])

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _row_to_txn(row: sqlite3.Row) -> Transaction:
        return Transaction(
            id=row["id"],
            txn_type=TxnType(row["txn_type"]),
            symbol=row["symbol"],
            trade_date=date.fromisoformat(row["trade_date"]),
            quantity=row["quantity"],
            price=row["price"],
            fee=row["fee"],
            currency=row["currency"],
            account=row["account"],
            ratio=row["ratio"],
            related_symbol=row["related_symbol"],
            note=row["note"],
        )
