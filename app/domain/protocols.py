"""Domain ports (Protocols). Concrete adapters live in app/infrastructure.

Keeping these as ``typing.Protocol`` lets services depend on behaviour, not on a
concrete SQLite/HTTP implementation — the single swap point for testing and for
future US -> TW data changes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Protocol

from app.domain.advice import OpinionCard
from app.domain.signals import EvidenceBundle, SignalOutput
from app.domain.transactions import Transaction


class LlmNarrator(Protocol):
    """Turns a frozen EvidenceBundle into a read-only OpinionCard.

    The narrator's ONLY input is the bundle (plus position context) — it cannot
    discover or invent signals. The AdviceService guardrail then validates that
    its citations reference only signals present in the bundle.
    """

    source: str

    def narrate(self, bundle: EvidenceBundle, context: Dict[str, Any]) -> OpinionCard: ...


class Signal(Protocol):
    """A deterministic, pure-classifier signal behind a thin network seam.

    Every implementation declares a stable signal_id + version and computes a
    SignalOutput for a symbol. New signals mirror the proven capex_monitor
    compute_*()/_fetch() pattern.
    """

    signal_id: str
    version: int

    def for_symbol(self, symbol: str) -> SignalOutput: ...


class HistoricalDataProvider(Protocol):
    """A source of historical daily closes (native currency) for reconstruction.

    Returns a pandas DataFrame indexed by date with one column per symbol.
    Typed as Any to keep the domain layer free of a pandas import.
    """

    def get_closes(self, symbols: List[str], period: str = "6mo") -> Any: ...


class MarketDataProvider(Protocol):
    """A source of current instrument prices (in each symbol's native currency).

    The existing PriceFetcher already satisfies this shape, so it is the first
    adapter. EDGAR/intraday/FinMind adapters slot in behind the same port.
    """

    def get_price(self, symbol: str) -> float: ...

    def get_prices(self, symbols: List[str]) -> Dict[str, float]: ...


class LedgerRepository(Protocol):
    """Append-only store of transactions."""

    def add(self, txn: Transaction) -> Transaction: ...

    def add_many(self, txns: List[Transaction]) -> List[Transaction]: ...

    def all(self) -> List[Transaction]: ...

    def by_symbol(self, symbol: str) -> List[Transaction]: ...

    def symbols(self) -> List[str]: ...

    def delete(self, txn_id: int) -> None: ...

    def count(self) -> int: ...
