"""Import Firstrade account-history CSV exports into the transaction ledger.

Firstrade columns: 日期, 交易類別, 數量, 說明, 代號, 賬戶類別, 價格, 金額.
The pure mapping (`map_row`, `inject_openings`) carries the test weight; reading
files and writing to the ledger are the IO seams.

Because the exports may not reach back to account opening, an opening BUY is
injected for any symbol whose running share balance would go negative (i.e. a
pre-history holding sold inside the window), priced at that symbol's earliest
seen price — so FIFO never oversells and fully-closed legacy positions net to 0.
"""

from __future__ import annotations

import csv
import logging
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from app.domain.transactions import CASH_SYMBOL, Transaction, TxnType

logger = logging.getLogger(__name__)

# Firstrade is USD; ADRs (e.g. TSM) trade in USD too.
_CCY = "USD"
_OPEN_DATE = date(2025, 1, 1)


def _clean_amount(value: str) -> float:
    value = (value or "").replace(",", "").strip()
    if not value:
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _parse_date(value: str) -> date:
    y, m, d = (value or "").strip().split("/")
    return date(int(y), int(m), int(d))


def map_row(row: Sequence[str]) -> Optional[Transaction]:
    """Map one Firstrade CSV row to a Transaction (None for ignorable rows)."""
    if len(row) < 8:
        return None
    date_s, kind, qty_s, _desc, sym, _acct, price_s, amt_s = row[:8]
    trade_date = _parse_date(date_s)
    qty = _clean_amount(qty_s)
    price = _clean_amount(price_s)
    amount = _clean_amount(amt_s)
    symbol = (sym or "").strip().upper()

    if kind == "買進":
        return Transaction(TxnType.BUY, symbol, trade_date, quantity=qty, price=price, currency=_CCY, note="firstrade")
    if kind == "賣出":
        return Transaction(TxnType.SELL, symbol, trade_date, quantity=abs(qty), price=price, currency=_CCY, note="firstrade")
    if kind == "存款":
        return Transaction(TxnType.DEPOSIT, CASH_SYMBOL, trade_date, quantity=amount, currency=_CCY, note="firstrade deposit")

    if kind == "其他" and abs(qty) > 1e-12:
        # Dividend reinvestment / fractional share movement (價格 is 0; derive it).
        per_share = price if price > 0 else (abs(amount) / abs(qty) if qty else 0.0)
        if qty > 0:
            return Transaction(TxnType.BUY, symbol, trade_date, quantity=qty, price=per_share, currency=_CCY, note="firstrade reinvest")
        return Transaction(TxnType.SELL, symbol, trade_date, quantity=abs(qty), price=per_share, currency=_CCY, note="firstrade")

    if kind in ("股息", "利息收入", "其他"):
        # Pure cash movement. Positive = income, negative = tax/fee adjustment.
        if amount >= 0:
            return Transaction(TxnType.DIVIDEND, symbol or CASH_SYMBOL, trade_date, quantity=amount, currency=_CCY, note=f"firstrade {kind}")
        return Transaction(TxnType.WITHDRAW, CASH_SYMBOL, trade_date, quantity=abs(amount), currency=_CCY, note=f"firstrade {kind} adj")

    return None


def inject_openings(txns: List[Transaction], open_date: date = _OPEN_DATE) -> List[Transaction]:
    """Prepend opening BUYs so no symbol's running share balance goes negative."""
    running: Dict[str, float] = defaultdict(float)
    lowest: Dict[str, float] = defaultdict(float)
    first_price: Dict[str, float] = {}

    for txn in sorted(txns, key=lambda t: t.trade_date):
        if txn.symbol == CASH_SYMBOL:
            continue
        if txn.txn_type == TxnType.BUY:
            running[txn.symbol] += txn.quantity
        elif txn.txn_type == TxnType.SELL:
            running[txn.symbol] -= txn.quantity
        lowest[txn.symbol] = min(lowest[txn.symbol], running[txn.symbol])
        if txn.symbol not in first_price and txn.price:
            first_price[txn.symbol] = txn.price

    openings = [
        Transaction(
            TxnType.BUY, symbol, open_date,
            quantity=round(-low, 6), price=first_price.get(symbol, 0.0),
            currency=_CCY, note="opening balance (pre-history estimate)",
        )
        for symbol, low in lowest.items()
        if low < -1e-9
    ]
    return openings + txns


def transactions_from_files(paths: Sequence[Path]) -> List[Transaction]:
    rows: List[List[str]] = []
    for path in paths:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            data = list(csv.reader(handle))[1:]  # skip header
        rows.extend(r for r in data if r and len(r) >= 8)
    mapped = [t for t in (map_row(r) for r in rows) if t is not None]
    return inject_openings(mapped)


def import_firstrade(paths: Sequence[Path], ledger) -> Dict:
    """Reset is the caller's responsibility; this appends parsed transactions."""
    txns = transactions_from_files(paths)
    ledger.add_many(txns)
    return {
        "imported": len(txns),
        "openings": sum(1 for t in txns if t.note.startswith("opening")),
        "symbols": sorted({t.symbol for t in txns if t.symbol != CASH_SYMBOL}),
    }
