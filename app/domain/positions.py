"""Derived position/portfolio state — the fold of the transaction ledger.

These are immutable value objects produced by the cost-basis engine
(app/services/cost_basis.py). They are never stored; they are recomputed from
the ledger, so they cannot drift out of sync with the source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class Position:
    """An open position in one symbol, with FIFO cost basis."""

    symbol: str
    quantity: float
    total_cost: float  # cost basis of the open shares, in `currency`
    average_cost: float  # total_cost / quantity
    currency: str
    realized_pl: float  # cumulative realized P&L for this symbol, in `currency`


@dataclass(frozen=True)
class PortfolioState:
    """The full derived state at a point in time."""

    positions: List[Position] = field(default_factory=list)
    cash: Dict[str, float] = field(default_factory=dict)  # currency -> balance
    realized_pl: Dict[str, float] = field(default_factory=dict)  # currency -> total
