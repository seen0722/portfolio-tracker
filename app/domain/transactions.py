"""Transaction domain model — the append-only source of truth.

A portfolio is no longer a mutable snapshot of holdings; it is the fold of an
immutable stream of transactions. This makes FIFO cost basis, realized P&L, and
corporate actions (splits/mergers/ticker changes) representable — none of which
the old ``Stock(symbol, shares, average_cost)`` snapshot could express.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional

# Sentinel symbol for pure-cash movements (deposits/withdrawals).
CASH_SYMBOL = "$CASH"


class TxnType(str, Enum):
    """The kinds of events that can appear in the ledger.

    Corporate actions are first-class from day one because they are the main
    cost-basis correctness landmine.
    """

    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    SPLIT = "split"  # ``ratio`` = new shares per old share (e.g. 4.0 for 4-for-1)
    MERGER = "merger"  # holding converts into ``related_symbol``
    TICKER_CHANGE = "ticker_change"  # symbol renamed to ``related_symbol``


@dataclass(frozen=True)
class Transaction:
    """A single immutable ledger event.

    ``quantity`` is share count for BUY/SELL, and a cash amount (in ``currency``)
    for DEPOSIT/WITHDRAW/DIVIDEND. ``price`` is per-share in ``currency``.
    ``id`` is assigned by the repository on insert (None before persistence).
    """

    txn_type: TxnType
    symbol: str
    trade_date: date
    quantity: float = 0.0
    price: float = 0.0
    fee: float = 0.0
    currency: str = "USD"
    account: str = "default"
    ratio: float = 0.0
    related_symbol: str = ""
    note: str = ""
    id: Optional[int] = None

    @property
    def cash_delta(self) -> float:
        """Signed cash impact in ``currency`` (positive = cash in).

        Pure and deterministic, so it carries unit-test weight and lets the cash
        balance be derived from the ledger rather than tracked separately.
        """
        if self.txn_type == TxnType.BUY:
            return -(self.quantity * self.price + self.fee)
        if self.txn_type == TxnType.SELL:
            return self.quantity * self.price - self.fee
        if self.txn_type in (TxnType.DEPOSIT, TxnType.DIVIDEND):
            return self.quantity - self.fee
        if self.txn_type == TxnType.WITHDRAW:
            return -(self.quantity + self.fee)
        # SPLIT / MERGER / TICKER_CHANGE move shares, not cash.
        return 0.0
