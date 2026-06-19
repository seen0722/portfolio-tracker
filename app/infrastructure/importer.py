"""One-shot migrator: portfolio.json -> seed transactions.

Each held stock becomes a single synthetic BUY at its average cost; each non-zero
cash balance becomes a DEPOSIT. A verification pass asserts the imported share
counts match the source before the JSON is retired (catches mapping bugs).
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Dict, List, Union

from app.domain.protocols import LedgerRepository
from app.domain.transactions import CASH_SYMBOL, Transaction, TxnType

# The original JSON has no acquisition dates; seed everything at one early date.
DEFAULT_IMPORT_DATE = date(2020, 1, 1)


def _currency_for(symbol: str) -> str:
    """TW listings (.TW / .TWO) report in TWD; everything else assumed USD."""
    return "TWD" if ".TW" in symbol.upper() else "USD"


def transactions_from_portfolio_dict(
    data: Dict, trade_date: date = DEFAULT_IMPORT_DATE
) -> List[Transaction]:
    """Pure transform: portfolio dict -> seed transactions.

    A holdings snapshot has no transaction history, so we synthesise an opening
    balance: each stock becomes a BUY at its average cost, and per currency we
    DEPOSIT (sum of buy costs + reported cash). The buys then draw that down,
    leaving net cash equal to the reported cash — instead of a spurious deficit.
    """
    buys: List[Transaction] = []
    buy_cost_by_ccy: Dict[str, float] = defaultdict(float)

    for stock in data.get("stocks", []):
        symbol = str(stock["symbol"]).strip().upper()
        shares = float(stock["shares"])
        if shares == 0:
            continue
        price = float(stock.get("average_cost", 0.0))
        currency = _currency_for(symbol)
        buy_cost_by_ccy[currency] += shares * price
        buys.append(
            Transaction(
                txn_type=TxnType.BUY,
                symbol=symbol,
                trade_date=trade_date,
                quantity=shares,
                price=price,
                currency=currency,
                note="imported from portfolio.json",
            )
        )

    reported_cash_by_ccy: Dict[str, float] = defaultdict(float)
    for cash in data.get("cash", []):
        reported_cash_by_ccy[str(cash["currency"]).strip().upper()] += float(cash["amount"])

    deposits: List[Transaction] = []
    for currency in sorted(set(buy_cost_by_ccy) | set(reported_cash_by_ccy)):
        opening = buy_cost_by_ccy.get(currency, 0.0) + reported_cash_by_ccy.get(currency, 0.0)
        if opening == 0:
            continue
        deposits.append(
            Transaction(
                txn_type=TxnType.DEPOSIT,
                symbol=CASH_SYMBOL,
                trade_date=trade_date,
                quantity=opening,
                currency=currency,
                note="opening balance (imported)",
            )
        )

    # Cash nets the same regardless of order, but list deposits first for clarity.
    return deposits + buys


def verify_import(data: Dict, txns: List[Transaction]) -> List[str]:
    """Return discrepancy messages; an empty list means the import is verified."""
    expected = {
        str(s["symbol"]).strip().upper(): float(s["shares"])
        for s in data.get("stocks", [])
        if float(s["shares"]) != 0
    }
    actual: Dict[str, float] = {}
    for txn in txns:
        if txn.txn_type == TxnType.BUY:
            actual[txn.symbol] = actual.get(txn.symbol, 0.0) + txn.quantity

    errors: List[str] = []
    for symbol, shares in expected.items():
        if abs(actual.get(symbol, 0.0) - shares) > 1e-6:
            errors.append(
                f"{symbol}: expected {shares} shares, imported {actual.get(symbol, 0.0)}"
            )
    return errors


def import_portfolio_json(
    path: Union[str, Path],
    ledger: LedgerRepository,
    trade_date: date = DEFAULT_IMPORT_DATE,
) -> Dict:
    """Load portfolio.json, verify, and append seed transactions to the ledger."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    txns = transactions_from_portfolio_dict(data, trade_date)
    errors = verify_import(data, txns)
    if errors:
        raise ValueError("Import verification failed: " + "; ".join(errors))

    ledger.add_many(txns)
    return {
        "imported": len(txns),
        "symbols": sorted({t.symbol for t in txns}),
        "verified": True,
    }
