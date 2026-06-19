"""FIFO cost-basis engine — pure transform from transactions to positions.

This is the correctness core of the whole app and carries the heaviest unit-test
weight. It is network-free and deterministic: feed it a list of Transactions and
it folds them into open positions (FIFO lots), realized P&L, and cash balances,
correctly handling splits, mergers, and ticker changes.

Fees are folded into cost basis (buy fees raise cost, sell fees reduce proceeds),
so realized P&L is net of costs on both sides.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from app.domain.positions import PortfolioState, Position
from app.domain.transactions import CASH_SYMBOL, Transaction, TxnType

_EPS = 1e-9


class _OpenLot:
    """Mutable FIFO lot used only inside the fold."""

    __slots__ = ("quantity", "cost_per_share")

    def __init__(self, quantity: float, cost_per_share: float) -> None:
        self.quantity = quantity
        self.cost_per_share = cost_per_share


def build_positions(txns: List[Transaction]) -> PortfolioState:
    """Fold transactions (oldest first) into the derived portfolio state."""
    lots: Dict[str, List[_OpenLot]] = defaultdict(list)
    currency_of: Dict[str, str] = {}
    realized: Dict[str, float] = defaultdict(float)  # per symbol
    cash: Dict[str, float] = defaultdict(float)  # per currency

    for txn in sorted(txns, key=lambda t: (t.trade_date, t.id or 0)):
        # Every event's cash impact flows through the one pure property.
        if txn.currency:
            cash[txn.currency] += txn.cash_delta

        if txn.txn_type == TxnType.BUY:
            currency_of[txn.symbol] = txn.currency
            total_cost = txn.quantity * txn.price + txn.fee
            cps = total_cost / txn.quantity if txn.quantity else txn.price
            lots[txn.symbol].append(_OpenLot(txn.quantity, cps))
        elif txn.txn_type == TxnType.SELL:
            _sell_fifo(lots[txn.symbol], txn, realized)
        elif txn.txn_type == TxnType.SPLIT:
            _apply_split(lots[txn.symbol], txn.ratio)
        elif txn.txn_type in (TxnType.MERGER, TxnType.TICKER_CHANGE):
            _apply_rename(lots, realized, currency_of, txn)
        # DIVIDEND / DEPOSIT / WITHDRAW are pure cash, already applied above.

    return _to_state(lots, currency_of, realized, cash)


def _sell_fifo(
    lot_list: List[_OpenLot], txn: Transaction, realized: Dict[str, float]
) -> None:
    held = sum(lot.quantity for lot in lot_list)
    if txn.quantity - held > _EPS:
        raise ValueError(
            f"Oversell: cannot sell {txn.quantity} {txn.symbol}, only {held} held"
        )

    proceeds = txn.quantity * txn.price - txn.fee
    cost_removed = 0.0
    remaining = txn.quantity
    while remaining > _EPS and lot_list:
        lot = lot_list[0]
        take = min(lot.quantity, remaining)
        cost_removed += take * lot.cost_per_share
        lot.quantity -= take
        remaining -= take
        if lot.quantity <= _EPS:
            lot_list.pop(0)

    realized[txn.symbol] += proceeds - cost_removed


def _apply_split(lot_list: List[_OpenLot], ratio: float) -> None:
    """Split: shares scale by ratio, cost-per-share inversely; total cost held."""
    if ratio <= 0:
        return
    for lot in lot_list:
        lot.quantity *= ratio
        lot.cost_per_share /= ratio


def _apply_rename(
    lots: Dict[str, List[_OpenLot]],
    realized: Dict[str, float],
    currency_of: Dict[str, str],
    txn: Transaction,
) -> None:
    """Merger / ticker change: move open lots (and realized P&L) to the new symbol."""
    old, new = txn.symbol, txn.related_symbol
    if not new:
        return
    ratio = txn.ratio if txn.ratio > 0 else 1.0
    for lot in lots.pop(old, []):
        if ratio != 1.0:
            lot.quantity *= ratio
            lot.cost_per_share /= ratio
        lots[new].append(lot)
    currency_of.setdefault(new, currency_of.get(old, "USD"))
    if old in realized:
        realized[new] += realized.pop(old)


def _to_state(
    lots: Dict[str, List[_OpenLot]],
    currency_of: Dict[str, str],
    realized: Dict[str, float],
    cash: Dict[str, float],
) -> PortfolioState:
    per_currency_realized: Dict[str, float] = defaultdict(float)
    for symbol, value in realized.items():
        per_currency_realized[currency_of.get(symbol, "USD")] += value

    positions: List[Position] = []
    for symbol, lot_list in lots.items():
        if symbol == CASH_SYMBOL:
            continue
        quantity = sum(lot.quantity for lot in lot_list)
        if quantity <= _EPS:
            continue  # fully closed; realized P&L still counted per currency
        total_cost = sum(lot.quantity * lot.cost_per_share for lot in lot_list)
        positions.append(
            Position(
                symbol=symbol,
                quantity=quantity,
                total_cost=total_cost,
                average_cost=total_cost / quantity,
                currency=currency_of.get(symbol, "USD"),
                realized_pl=realized.get(symbol, 0.0),
            )
        )

    positions.sort(key=lambda p: p.symbol)
    return PortfolioState(
        positions=positions,
        cash=dict(cash),
        realized_pl=dict(per_currency_realized),
    )
