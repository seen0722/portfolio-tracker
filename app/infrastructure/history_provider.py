"""Historical daily closes via yfinance — the seam for NAV reconstruction.

Network-bound and isolated here so the NAV reconstruction logic stays pure and
unit-testable with a synthetic closes frame.
"""

from __future__ import annotations

import logging
from typing import List

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class YahooHistoryProvider:
    """Fetch adjusted daily closes for a set of symbols over a period."""

    def get_closes(self, symbols: List[str], period: str = "6mo") -> pd.DataFrame:
        if not symbols:
            return pd.DataFrame()
        try:
            # auto_adjust=False -> raw "Close", matching the live (raw) price
            # basis used by valuation, so the reconstructed series and today's
            # live snapshot are on the same scale (no split/dividend seam).
            data = yf.download(
                symbols,
                period=period,
                progress=False,
                auto_adjust=False,
                threads=True,
            )
        except Exception as exc:  # degrade to empty -> caller keeps prior history
            logger.warning("Historical fetch failed for %s: %s", symbols, exc)
            return pd.DataFrame()

        if data is None or data.empty:
            return pd.DataFrame()

        closes = data["Close"] if "Close" in getattr(data, "columns", []) else data
        if isinstance(closes, pd.Series):
            closes = closes.to_frame(name=symbols[0])
        return closes.dropna(how="all")
