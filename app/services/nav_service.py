"""NAV service — reconstruct and record the real daily portfolio value series.

`reconstruct_nav_series` is a pure transform (holdings x historical closes + cash
-> NAV series), unit-tested with a synthetic frame. NavService wires it to the
ledger, the historical-data seam, and the NAV repository.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import pandas as pd

from app.domain.protocols import (
    HistoricalDataProvider,
    LedgerRepository,
    MarketDataProvider,
)
from app.infrastructure.market_data import PriceFetchError
from app.infrastructure.nav_repository import NavRepository
from app.services.cost_basis import build_positions

logger = logging.getLogger(__name__)

_DEFAULT_FX_USDTWD = 32.0  # fallback only; live rate is fetched when possible

# A holding as fed to the pure reconstructor: (symbol, shares, currency).
Holding = Tuple[str, float, str]


def reconstruct_nav_series(
    holdings: List[Holding],
    closes: pd.DataFrame,
    cash_usd: float,
    fx_usdtwd: float,
) -> pd.DataFrame:
    """Pure transform: value current holdings at each day's close, add cash.

    Approximation: uses *current* holdings across the window (exact when there
    were no trades in the window, which holds for a snapshot seeded at one date).
    """
    if closes is None or closes.empty:
        return pd.DataFrame(columns=["date", "total_usd", "total_twd", "daily_return_pct"])

    # Clean cross-market calendar gaps and bad prints: treat 0/inf as missing,
    # then carry the last known price forward/back. Without this, a TW-holiday
    # NaN (while US trades) drops a whole holding for a day and corrupts the
    # volatility/drawdown analytics with a spurious ~one-day cliff.
    closes = closes.replace(0, float("nan")).replace([float("inf"), float("-inf")], float("nan"))
    closes = closes.ffill().bfill()

    nav_usd = pd.Series(0.0, index=closes.index)
    for symbol, shares, currency in holdings:
        if symbol not in closes.columns:
            continue
        col = closes[symbol].astype(float)
        value_usd = col * shares / fx_usdtwd if currency == "TWD" else col * shares
        nav_usd = nav_usd.add(value_usd, fill_value=0.0)

    nav_usd = nav_usd + cash_usd
    nav_usd = nav_usd.dropna()

    df = pd.DataFrame(
        {
            "date": pd.to_datetime(nav_usd.index).strftime("%Y-%m-%d"),
            "total_usd": nav_usd.values,
        }
    )
    df["total_twd"] = df["total_usd"] * fx_usdtwd
    df["daily_return_pct"] = df["total_usd"].pct_change().fillna(0.0) * 100.0
    return df


class NavService:
    """Reconstruct, record, and read the daily NAV series."""

    def __init__(
        self,
        ledger: LedgerRepository,
        history_provider: HistoricalDataProvider,
        nav_repository: NavRepository,
        price_provider: MarketDataProvider,
    ) -> None:
        self.ledger = ledger
        self.history_provider = history_provider
        self.nav_repository = nav_repository
        self.price_provider = price_provider

    def history(self) -> pd.DataFrame:
        return self.nav_repository.load()

    def ensure_history(self, period: str = "6mo") -> pd.DataFrame:
        """Reconstruct from historical closes if no NAV series exists yet."""
        if self.nav_repository.count() == 0:
            self.reconstruct(period)
        return self.history()

    def series_for(self, period: str = "6mo") -> pd.DataFrame:
        """Reconstruct the NAV series for a period without persisting it.

        Used by the chart's time-range tabs; valuing *current* holdings back over
        the window (exact for a snapshot held across the window).
        """
        state = build_positions(self.ledger.all())
        holdings: List[Holding] = [
            (pos.symbol, pos.quantity, pos.currency) for pos in state.positions
        ]
        if not holdings:
            return pd.DataFrame(columns=["date", "total_usd", "total_twd", "daily_return_pct"])
        symbols = [h[0] for h in holdings]
        closes = self.history_provider.get_closes(symbols, period)
        fx = self._fx_usdtwd()
        cash_usd = sum(self._to_usd(amount, ccy, fx) for ccy, amount in state.cash.items())
        return reconstruct_nav_series(holdings, closes, cash_usd, fx)

    def reconstruct(self, period: str = "6mo") -> pd.DataFrame:
        df = self.series_for(period)
        if not df.empty:
            self.nav_repository.replace_all(df)
            logger.info("Reconstructed %d NAV points over %s", len(df), period)
        return self.history()

    def snapshot(self, total_usd: float, total_twd: float, as_of: str) -> None:
        """Record today's real NAV from the live valuation."""
        self.nav_repository.upsert(as_of, total_usd, total_twd)

    def _fx_usdtwd(self) -> float:
        try:
            rate = self.price_provider.get_price("USDTWD=X")
            if rate and rate > 0:
                return float(rate)
        except PriceFetchError:
            pass
        return _DEFAULT_FX_USDTWD

    @staticmethod
    def _to_usd(amount: float, currency: str, fx_usdtwd: float) -> float:
        if currency == "USD":
            return amount
        if currency == "TWD":
            return amount / fx_usdtwd
        return amount  # unknown currency: treat as USD-equivalent
